"""Evidence-first agent: plan, query, compare, explain, and verify."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from whytrace.llm import _setting, generate
from whytrace.verifier import verify_report
from whytrace.world_model.context import ContextBuilderService
from whytrace.world_model.ingest import IngestPipelineService
from whytrace.world_model.store import WorldStoreService
from whytrace.zetaris_client import run_query

STORE_SQL = """WITH monthly AS (
 SELECT s.s_store_id AS store_id,d.d_year AS year,d.d_moy AS month,SUM(ss.ss_net_paid) AS revenue
 FROM store_sales ss JOIN store s ON ss.ss_store_sk=s.s_store_sk
 JOIN date_dim d ON ss.ss_sold_date_sk=d.d_date_sk GROUP BY 1,2,3
)
SELECT store_id,year,month,revenue,LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month) AS prior_revenue,
ROUND(100.0*(revenue-LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month)) /
NULLIF(LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month),0),2) AS pct_change
FROM monthly ORDER BY store_id,year,month"""
SCHEMA = "Tables: store(s_store_sk,s_store_id), item(i_item_sk,i_category), date_dim(d_date_sk,d_year,d_moy), store_sales(ss_sold_date_sk,ss_store_sk,ss_item_sk,ss_net_paid), store_returns(sr_returned_date_sk,sr_store_sk,sr_item_sk,sr_return_amt), inventory(inv_date_sk,inv_store_sk,inv_item_sk,inv_quantity_on_hand)."
MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}


def _append_trace(path: Path, step: str, model: str, sql: str = "", row_count=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "step": step,
                            "model": model, "sql": sql, "row_count": row_count}) + "\n")


def _json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{[\s\S]*\}", text or "")
        try:
            return json.loads(match.group()) if match else {}
        except json.JSONDecodeError:
            return {}


def _sql_text(text: str) -> str:
    match = re.search(r"```(?:sql)?\s*(.*?)```", text or "", re.I | re.S)
    sql = match.group(1).strip() if match else (text or "").strip()
    start = re.search(r"\b(SELECT|WITH)\b", sql, re.I)
    return sql[start.start():].strip() if start else sql


def _month_year(question: str, rows: list[dict]) -> tuple[int | None, int | None]:
    q = question.lower()
    month = next((num for name, num in MONTHS.items() if re.search(rf"\b{name}\b", q)), None)
    year_match = re.search(r"\b20\d{2}\b", q)
    year = int(year_match.group()) if year_match else None
    months = sorted((int(r["year"]), int(r["month"])) for r in rows if r.get("year") is not None and r.get("month") is not None)
    if month is None and months:
        year, month = months[-1]
    if year is None and month and months:
        year = next((y for y, m in reversed(months) if m == month), months[-1][0])
    return month, year


def _pct(row: dict) -> float | None:
    try:
        if row.get("pct_change") is not None:
            return float(row["pct_change"])
        if row.get("prior_revenue") not in (None, 0):
            return 100 * (float(row["revenue"]) - float(row["prior_revenue"])) / float(row["prior_revenue"])
    except (TypeError, ValueError, KeyError):
        return None
    return None


def _find_row(rows: list[dict], **fields):
    return next((i for i, row in enumerate(rows) if all(str(row.get(k)).upper() == str(v).upper() for k, v in fields.items())), None)


def _row_for(rows: list[dict], store: str | None, month: int | None, year: int | None, direction: str = "largest_change"):
    candidates = [(i, r) for i, r in enumerate(rows) if r.get("revenue") is not None and (month is None or int(r["month"]) == month) and (year is None or int(r["year"]) == year)]
    if store:
        candidates = [(i, r) for i, r in candidates if str(r.get("store_id", "")).upper() == store.upper()]
    if direction == "increase":
        return max(candidates, key=lambda pair: _pct(pair[1]) if _pct(pair[1]) is not None else float("-inf")) if candidates else (None, None)
    if direction == "decrease":
        return min(candidates, key=lambda pair: _pct(pair[1]) if _pct(pair[1]) is not None else float("inf")) if candidates else (None, None)
    return max(candidates, key=lambda pair: abs(_pct(pair[1]) or 0)) if candidates else (None, None)


def _previous_index(rows: list[dict], row: dict):
    year, month, store = int(row["year"]), int(row["month"]), row["store_id"]
    py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
    return _find_row(rows, store_id=store, year=py, month=pm)


def _question_intent(question: str) -> str:
    q = question.lower()
    if any(word in q for word in ("return", "refund")) and not any(word in q for word in ("explain", "account for", "cause", "drive")):
        return "returns"
    if any(word in q for word in ("inventory", "stock level", "stockout")) and not any(word in q for word in ("explain", "account for", "cause", "drive")):
        return "inventory"
    if any(word in q for word in ("category", "categories", "product mix", "item mix", "which product")):
        return "category"
    return "store"


def _dimension_driver(question: str, intent: str, results: list[dict]):
    spec = {"returns": ("return", "category", "return_amount", "return"),
            "category": ("category", "category", "revenue", "revenue"),
            "inventory": ("inventory", "store_id", "inventory_qty", "units")}.get(intent)
    if not spec:
        return None
    marker, key, value_col, unit = spec
    result = next((r for r in results if marker in (r["name"] + r["question"]).lower()
                   and r["rows"] and value_col in r["rows"][0]), None)
    if result is None:
        return None
    rows = result["rows"]
    month, year = _month_year(question, rows)
    if month is None or year is None:
        return None
    focus_month, focus_year = month, year
    prior_month, prior_year = ((month - 1, year) if month > 1 else (12, year - 1))
    target_match = re.search(r"\b(S\d+|Electronics|Home|Apparel)\b", question, re.I)
    target = target_match.group(1).lower() if target_match else None
    pairs = []
    for idx, row in enumerate(rows):
        if int(row.get("month", -1)) != focus_month or int(row.get("year", -1)) != focus_year or row.get(value_col) is None:
            continue
        label = row.get(key)
        if target and str(label).lower() != target:
            continue
        before = _find_row(rows, **{key: label, "year": prior_year, "month": prior_month})
        if before is not None and rows[before].get(value_col) is not None:
            before_value, after_value = float(rows[before][value_col]), float(row[value_col])
            pairs.append((after_value - before_value, idx, before, label, before_value, after_value))
    if not pairs:
        return None
    q = question.lower()
    if any(word in q for word in ("grow", "increase", "rise", "higher", "up")):
        pair = max(pairs)
    elif any(word in q for word in ("drop", "fall", "decrease", "decline", "lower", "down", "lose")):
        pair = min(pairs)
    else:
        pair = max(pairs, key=lambda p: abs(p[0]))
    delta, idx, before, label, before_value, after_value = pair
    subject = f"{label} {intent}"
    period = f"{focus_year}-{focus_month:02d}"
    if unit == "return":
        claim = f"{label} returns moved from ${before_value:,.0f} to ${after_value:,.0f} month over month."
    elif unit == "revenue":
        claim = f"{label} category revenue moved from ${before_value:,.0f} to ${after_value:,.0f} month over month."
    else:
        claim = f"{label} average inventory moved from {before_value:,.0f} to {after_value:,.0f} units month over month."
    eid = result["evidence"]["evidence_id"]
    return {"title": f"{subject.title()} changed in {period}", "claim": claim,
            "confidence": 0.84, "evidence_ids": [eid],
            "numeric_claims": [
                {"label": f"Prior period {unit}", "evidence_id": eid, "row_index": before, "column": value_col, "value": rows[before][value_col]},
                {"label": f"Focus period {unit}", "evidence_id": eid, "row_index": idx, "column": value_col, "value": rows[idx][value_col]},
            ], "model": result["model"], "period": period, "subject": subject}


def run_agent(question: str, *, store: WorldStoreService | None = None, query_fn=run_query,
              generator=generate, trace_path: str | Path | None = None, on_step=None) -> dict:
    def announce(message: str):
        if on_step:
            on_step(message)
    log_dir = Path(os.getenv("WHYTRACE_LOG_DIR", "logs"))
    trace_path = Path(trace_path or log_dir / "trace.jsonl")
    store = store or WorldStoreService()
    ingest = IngestPipelineService(store=store)
    evidence_source = "duckdb" if _setting("SAMPLE_MODE", "true").strip().lower() in {"1", "true", "yes", "on"} else "zetaris"
    plan_prompt = ("Plan exactly 4 diverse, testable SQL investigations for the user's retail metric question. "
                   "Return only JSON: {\"hypotheses\":[{\"name\":string,\"question\":string}]}. "
                   "Include store revenue, returns, product category sales, and inventory.\nQUESTION: " + question)
    plan_text, plan_model = generator("deep", plan_prompt)
    _append_trace(trace_path, "plan", plan_model)
    announce(f"Investigation plan ready · {plan_model}")
    hypotheses = _json_object(plan_text).get("hypotheses", [])
    if not isinstance(hypotheses, list) or not hypotheses:
        hypotheses = [
            {"name": "Store revenue trend", "question": "Compare monthly net sales by store."},
            {"name": "Returns trend", "question": "Compare monthly returns by item category."},
            {"name": "Product mix trend", "question": "Compare monthly net sales by item category."},
            {"name": "Inventory trend", "question": "Compare monthly inventory by store."},
        ]

    results = []
    for idx, hypothesis in enumerate(hypotheses[:5]):
        name = str(hypothesis.get("name", f"Hypothesis {idx + 1}"))
        prompt = str(hypothesis.get("question", ""))
        announce(f"Testing hypothesis {idx + 1}/{min(len(hypotheses), 5)} · {name}")
        sql_prompt = ("Write exactly one read-only SQL query for this test. Return SQL only, no commentary or markdown. "
                     f"Use only this schema: {SCHEMA}\nHypothesis: {name}\nTest: {prompt}\n"
                     "For store revenue, return aliases store_id, year, month, revenue, prior_revenue, pct_change. "
                     "For returns, return category, year, month, return_amount. For category sales return category, year, month, revenue. "
                     "For inventory return store_id, year, month, inventory_qty. Include the focus month and its immediately preceding month; do not filter away the comparison period.")
        sql_text, model = generator("fast", sql_prompt)
        sql = _sql_text(sql_text)
        try:
            rows = query_fn(sql)
        except Exception:
            # Invalid model SQL never enters the evidence store; use the safe local query template.
            from whytrace.llm import _offline
            sql, model = _offline("fast", "HYPOTHESIS: " + prompt)
            rows = query_fn(sql)
        if "store" in name.lower() and "inventory" not in name.lower() and rows and not {"store_id", "year", "month", "revenue", "pct_change"}.issubset(rows[0]):
            from whytrace.llm import _offline
            sql, model = _offline("fast", "monthly net sales by store")
            rows = query_fn(sql)
        evidence = ingest.ingest({"sql": sql, "rows": rows, "model": model, "source": evidence_source})
        _append_trace(trace_path, f"query:{name}", model, sql, len(rows))
        announce(f"Query complete · {len(rows)} rows · {model}")
        results.append({"name": name, "question": prompt, "sql": sql, "model": model,
                        "rows": rows, "evidence": evidence})

    store_result = next((r for r in results if r["rows"] and {"store_id", "year", "month", "revenue", "pct_change"}.issubset(r["rows"][0])), None)
    if store_result is None:
        from whytrace.llm import _offline
        sql, model = _offline("fast", "monthly net sales by store")
        rows = query_fn(sql)
        ev = ingest.ingest({"sql": sql, "rows": rows, "model": model, "source": evidence_source})
        _append_trace(trace_path, "query:Store revenue trend (required comparison)", model, sql, len(rows))
        store_result = {"name": "Store revenue trend", "question": "Compare monthly revenue by store", "sql": sql,
                        "model": model, "rows": rows, "evidence": ev}
        results.insert(0, store_result)

    store_rows = store_result["rows"]
    month, year = _month_year(question, store_rows)
    lowered_question = question.lower()
    if any(word in lowered_question for word in ("grow", "increase", "rise", "higher")):
        store_direction = "increase"
    elif any(word in lowered_question for word in ("drop", "fall", "decrease", "decline", "lower")):
        store_direction = "decrease"
    else:
        store_direction = "largest_change"
    requested_store = re.search(r"\bS\d+\b", question, re.I)
    target_store = requested_store.group().upper() if requested_store else None
    current_idx, current = _row_for(store_rows, target_store, month, year, store_direction)
    if current is None and target_store:
        current_idx, current = _row_for(store_rows, None, month, year, store_direction)
    prev_idx = _previous_index(store_rows, current) if current else None
    store_eid = store_result["evidence"]["evidence_id"]
    drivers, ruled = [], []
    if current is not None and prev_idx is not None:
        previous = store_rows[prev_idx]
        pct = _pct(current)
        if pct is None:
            pct = (float(current["revenue"]) - float(previous["revenue"])) / float(previous["revenue"]) * 100
        store_id = current.get("store_id", "store")
        period = f"{int(current['year'])}-{int(current['month']):02d}"
        title = f"{store_id} revenue fell in {period}" if pct < 0 else f"{store_id} revenue changed in {period}"
        drivers.append({"title": title,
                        "claim": f"{store_id} revenue moved from ${float(previous['revenue']):,.0f} to ${float(current['revenue']):,.0f} month over month ({pct:+.1f}%).",
                        "confidence": min(0.98, 0.72 + abs(pct) / 100), "evidence_ids": [store_eid],
                        "numeric_claims": [
                            {"label": "Prior month revenue", "evidence_id": store_eid, "row_index": prev_idx, "column": "revenue", "value": previous["revenue"]},
                            {"label": "Focus month revenue", "evidence_id": store_eid, "row_index": current_idx, "column": "revenue", "value": current["revenue"]},
                            {"label": "Month-over-month change", "evidence_id": store_eid, "row_index": current_idx, "column": "pct_change", "value": current["pct_change"]},
                        ], "model": store_result["model"], "period": period, "store_id": store_id})
    intent = _question_intent(question)
    if intent != "store":
        dimensional_driver = _dimension_driver(question, intent, results)
        drivers = [dimensional_driver] if dimensional_driver else []
    focus_month, focus_year = (int(current["month"]), int(current["year"])) if current else (month, year)
    prior_month, prior_year = ((focus_month - 1, focus_year) if focus_month and focus_month > 1 else (12, focus_year - 1)) if focus_month else (None, None)
    return_result = next((r for r in results if "return" in (r["name"] + r["question"]).lower()), None)
    if return_result and intent == "store":
        rr, eid = return_result["rows"], return_result["evidence"]["evidence_id"]
        pairs = []
        for i, row in enumerate(rr):
            if int(row.get("month", -1)) == focus_month and int(row.get("year", -1)) == focus_year:
                before = _find_row(rr, category=row.get("category"), year=prior_year, month=prior_month)
                if before is not None:
                    delta = float(row.get("return_amount", 0)) - float(rr[before].get("return_amount", 0))
                    if delta > 0:
                        pairs.append((delta, i, before, row))
        if pairs:
            delta, i, before_i, row = max(pairs)
            sales_loss = (float(store_rows[prev_idx]["revenue"]) - float(current["revenue"])) if current is not None and prev_idx is not None else float("inf")
            title = f"{row['category']} returns rose, but are not the primary driver" if delta < sales_loss else f"{row['category']} returns increased; check scope"
            ruled.append({"title": title,
                          "claim": f"{row['category']} returns increased from ${float(rr[before_i]['return_amount']):,.0f} to ${float(row['return_amount']):,.0f}; the store sales evidence shows the larger revenue movement.",
                          "confidence": 0.92, "evidence_ids": [eid] + ([store_eid] if current is not None else []),
                          "numeric_claims": [
                              {"label": "Prior period returns", "evidence_id": eid, "row_index": before_i, "column": "return_amount", "value": rr[before_i]["return_amount"]},
                              {"label": "Focus period returns", "evidence_id": eid, "row_index": i, "column": "return_amount", "value": row["return_amount"]},
                          ], "model": return_result["model"]})
    for result in results:
        if result is store_result or result is return_result:
            continue
        ruled.append({"title": result["name"] + " checked", "claim": f"The {result['name'].lower()} query ran; its rows are available for review.",
                      "confidence": 0.72, "evidence_ids": [result["evidence"]["evidence_id"]],
                      "numeric_claims": [], "model": result["model"]})

    evidence_ids = list(dict.fromkeys(r["evidence"]["evidence_id"] for r in results))
    answer_context = {"store": drivers[0].get("subject", drivers[0].get("store_id", "retail metric")) if drivers else "retail trend",
                      "period": drivers[0]["period"] if drivers else "the requested period",
                      "driver": drivers[0]["title"] if drivers else "no month-over-month change could be verified",
                      "evidence_ids": evidence_ids,
                      "returns_check": ruled[0]["title"] if ruled and return_result else "returns were not conclusive"}
    announce("Skeptic agent is independently reviewing the evidence")
    skeptic_prompt = ("You are the independent skeptic in a multi-agent retail analytics team. "
                      "Check whether the proposed result is actually supported by the supplied query rows. "
                      "Do not invent facts, numbers, causes, or new claims. Return only JSON with keys status, review, contradictions. "
                      "Keep review to one concise sentence. Any contradiction must quote an evidence_id and a row/field.\n"
                      "INVESTIGATION: " + json.dumps({"question": question, "proposed_result": answer_context,
                                                       "queries": [{"name": r["name"], "evidence_id": r["evidence"]["evidence_id"],
                                                       "rows": r["rows"][:20]} for r in results]}, default=str))
    skeptic_text, skeptic_model = generator("skeptic", skeptic_prompt)
    skeptic_payload = _json_object(skeptic_text)
    skeptic_review = {"status": skeptic_payload.get("status", "reviewed"),
                      "review": skeptic_payload.get("review", skeptic_text),
                      "contradictions": skeptic_payload.get("contradictions", []),
                      "model": skeptic_model, "evidence_ids": evidence_ids}
    _append_trace(trace_path, "skeptic_review", skeptic_model)
    explain_prompt = "EXPLANATION:\n" + json.dumps(answer_context)
    explanation, explanation_model = generator("deep", explain_prompt)
    _append_trace(trace_path, "explanation", explanation_model)
    announce("Re-running cited SQL and checking claim values")
    actions = {
        "returns": ["Inspect the category's return reasons and product quality signals.", "Compare return rates against unit sales before changing policy."],
        "category": ["Review promotions, pricing, and availability for the category.", "Compare the category's contribution with the total store trend."],
        "inventory": ["Check replenishment timing and stockout events for the affected store.", "Compare average on-hand stock with the sales trend before changing orders."],
        "store": ["Inspect the affected store's staffing, stock availability, and promotions for the focus month.", "Review the returns evidence before taking action."],
    }[intent]
    report = {"question": question, "ranked_drivers": drivers, "ruled_out": ruled,
              "explanation": explanation, "explanation_model": explanation_model,
              "skeptic_review": skeptic_review,
              "explanation_evidence_ids": evidence_ids,
              "recommended_actions": actions,
              "evidence_ids": evidence_ids, "model_plan": plan_model, "hypotheses": results,
              "agent_roles": {"planner": plan_model, "sql_investigator": list(dict.fromkeys(r["model"] for r in results)),
                              "skeptic": skeptic_model, "explainer": explanation_model}}
    used_models = [plan_model, skeptic_model, explanation_model] + [r["model"] for r in results]
    used_live = [model for model in used_models if str(model).lower().startswith(("meterless", "nvidia"))]
    if used_live and not any("fallback" in str(model).lower() or str(model).lower().startswith("offline") for model in used_models):
        providers = {"nvidia" if str(model).lower().startswith("nvidia") else "meterless" for model in used_live}
        report["agent_mode"] = "Multi-agent · Meterless + NVIDIA Nemotron" if len(providers) == 2 else "NVIDIA Nemotron agents" if "nvidia" in providers else "Meterless Nightshift agents"
    else:
        report["agent_mode"] = "Multi-agent · live model with offline fallback" if used_live else "Offline evidence agent"
    verify_report(report, store, query_fn=query_fn)
    announce("Evidence verification complete")
    report["context"] = ContextBuilderService(store).build_context(evidence_ids)
    return report
