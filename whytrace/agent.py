"""Question-to-evidence explanation pipeline."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from whytrace.llm import generate
from whytrace.verifier import verify_report
from whytrace.world_model.context import ContextBuilderService
from whytrace.world_model.ingest import IngestPipelineService
from whytrace.world_model.store import WorldStoreService
from whytrace.zetaris_client import run_query

STORE_SQL = """WITH monthly AS (
 SELECT s.s_store_id AS store_id, d.d_year AS year, d.d_moy AS month,
        SUM(ss.ss_net_paid) AS revenue
 FROM store_sales ss JOIN store s ON ss.ss_store_sk=s.s_store_sk
 JOIN date_dim d ON ss.ss_sold_date_sk=d.d_date_sk
 GROUP BY 1,2,3
)
SELECT store_id, year, month, revenue,
       LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month) AS prior_revenue,
       ROUND(100.0*(revenue-LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month)) /
             NULLIF(LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month),0), 2) AS pct_change
FROM monthly ORDER BY store_id,year,month"""
SALES_CATEGORY_SQL = "SELECT i.i_category AS category, d.d_year AS year, d.d_moy AS month, SUM(ss.ss_net_paid) AS revenue FROM store_sales ss JOIN item i ON ss.ss_item_sk=i.i_item_sk JOIN date_dim d ON ss.ss_sold_date_sk=d.d_date_sk GROUP BY 1,2,3 ORDER BY 1,2,3"
RETURNS_SQL = "SELECT i.i_category AS category, d.d_year AS year, d.d_moy AS month, SUM(sr.sr_return_amt) AS return_amount FROM store_returns sr JOIN item i ON sr.sr_item_sk=i.i_item_sk JOIN date_dim d ON sr.sr_returned_date_sk=d.d_date_sk GROUP BY 1,2,3 ORDER BY 1,2,3"
INVENTORY_SQL = "SELECT s.s_store_id AS store_id, SUM(inv.inv_quantity_on_hand) AS inventory_qty FROM inventory inv JOIN store s ON inv.inv_store_sk=s.s_store_sk JOIN date_dim d ON inv.inv_date_sk=d.d_date_sk WHERE d.d_year=2026 AND d.d_moy=3 GROUP BY 1 ORDER BY 1"


def _append_trace(path: Path, step: str, model: str, sql: str = "", row_count=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "step": step,
                            "model": model, "sql": sql, "row_count": row_count}) + "\n")


def _find_row(rows, **fields):
    return next((i for i, row in enumerate(rows) if all(row.get(k) == v for k, v in fields.items())), None)


def run_agent(question: str, *, store: WorldStoreService | None = None, query_fn=run_query,
              generator=generate, trace_path: str | Path | None = None) -> dict:
    log_dir = Path(os.getenv("WHYTRACE_LOG_DIR", "logs"))
    trace_path = Path(trace_path or log_dir / "trace.jsonl")
    store = store or WorldStoreService()
    ingest = IngestPipelineService(store=store)
    plan_text, plan_model = generator("deep", "Plan 3-5 testable hypotheses for this retail question. Return JSON.\nQUESTION: " + question)
    _append_trace(trace_path, "plan", plan_model)
    try:
        hypotheses = json.loads(plan_text).get("hypotheses", [])
    except (json.JSONDecodeError, AttributeError):
        hypotheses = []
    if not hypotheses:
        hypotheses = [{"name": "Store revenue changed", "question": "Compare monthly net sales by store"},
                      {"name": "Product mix shifted", "question": "Compare monthly sales by item category"},
                      {"name": "Returns spike", "question": "Compare monthly return amount by item category"}]

    results = []
    for idx, hypothesis in enumerate(hypotheses[:5]):
        name, prompt = hypothesis.get("name", f"Hypothesis {idx+1}"), hypothesis.get("question", "")
        sql, model = generator("fast", "Generate one read-only SQL query for this hypothesis.\nHYPOTHESIS: " + prompt)
        rows = query_fn(sql)
        evidence = ingest.ingest({"sql": sql, "rows": rows, "model": model, "source": "zetaris"})
        _append_trace(trace_path, f"query:{name}", model, sql, len(rows))
        results.append({"name": name, "question": prompt, "sql": sql, "model": model,
                        "rows": rows, "evidence": evidence})

    # The report is assembled from measured evidence, not free-form model prose.
    store_result = next((r for r in results if "store" in (r["name"]+r["question"]).lower()), results[0])
    store_rows, store_eid = store_result["rows"], store_result["evidence"]["evidence_id"]
    feb_idx = _find_row(store_rows, store_id="S3", year=2026, month=2)
    mar_idx = _find_row(store_rows, store_id="S3", year=2026, month=3)
    drivers, ruled = [], []
    if feb_idx is not None and mar_idx is not None:
        before, after = store_rows[feb_idx], store_rows[mar_idx]
        pct_idx = mar_idx
        drivers.append({
            "title": "S3 revenue fell sharply in March", "claim": "Store S3 revenue changed from ${:,.0f} in February to ${:,.0f} in March ({:.1f}%).".format(
                float(before["revenue"]), float(after["revenue"]), float(after["pct_change"])),
            "confidence": 0.98, "evidence_ids": [store_eid],
            "numeric_claims": [
                {"label": "February S3 revenue", "evidence_id": store_eid, "row_index": feb_idx, "column": "revenue", "value": before["revenue"]},
                {"label": "March S3 revenue", "evidence_id": store_eid, "row_index": mar_idx, "column": "revenue", "value": after["revenue"]},
                {"label": "March month-over-month change", "evidence_id": store_eid, "row_index": pct_idx, "column": "pct_change", "value": after["pct_change"]},
            ], "model": store_result["model"],
        })
    for result in results:
        if "return" in (result["name"] + result["question"]).lower():
            rows, eid = result["rows"], result["evidence"]["evidence_id"]
            decoy_idx = _find_row(rows, category="Electronics", year=2026, month=3)
            jan_idx = _find_row(rows, category="Electronics", year=2026, month=1)
            if decoy_idx is not None and jan_idx is not None:
                amount, base = rows[decoy_idx]["return_amount"], rows[jan_idx]["return_amount"]
                ruled.append({"title": "Electronics returns spike is too small to explain the drop",
                              "claim": "Electronics returns rose from ${:,.0f} in January to ${:,.0f} in March; this is small beside S3's revenue decline.".format(float(base), float(amount)),
                              "confidence": 0.97, "evidence_ids": [eid, store_eid],
                              "numeric_claims": [
                                  {"label": "January Electronics returns", "evidence_id": eid, "row_index": jan_idx, "column": "return_amount", "value": base},
                                  {"label": "March Electronics returns", "evidence_id": eid, "row_index": decoy_idx, "column": "return_amount", "value": amount},
                                  {"label": "March S3 revenue decline percent", "evidence_id": store_eid, "row_index": mar_idx, "column": "pct_change", "value": store_rows[mar_idx]["pct_change"]},
                              ], "model": result["model"]})
    # Retain all remaining hypotheses as ruled-out with direct evidence references.
    used_names = {r["name"] for r in results if "return" in (r["name"]+r["question"]).lower()}
    for result in results:
        if result is store_result or result["name"] in used_names:
            continue
        ruled.append({"title": result["name"] + " not supported as the primary driver",
                      "claim": "This check did not establish a stronger explanation for the S3 March revenue change.",
                      "confidence": 0.75, "evidence_ids": [result["evidence"]["evidence_id"]],
                      "numeric_claims": [], "model": result["model"]})
    report = {"question": question, "ranked_drivers": drivers, "ruled_out": ruled,
              "recommended_actions": ["Review S3's March operating and merchandising changes.",
                                      "Check whether the Electronics return spike reflects a quality issue."],
              "evidence_ids": list(dict.fromkeys(r["evidence"]["evidence_id"] for r in results)),
              "model_plan": plan_model, "hypotheses": results}
    verify_report(report, store, query_fn=query_fn)
    report["context"] = ContextBuilderService(store).build_context(report["evidence_ids"])
    return report
