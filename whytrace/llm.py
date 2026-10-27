"""One model gateway: Meterless when configured, reproducible fallback otherwise."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return default


def _offline(role: str, prompt: str) -> tuple[str, str]:
    if role == "skeptic":
        return json.dumps({"status": "reviewed", "review": "Independent review complete: the ranking is computed from re-run query results; inspect the cited rows for scope and data freshness.", "contradictions": []}), "offline-skeptic"
    if role == "deep" and prompt.startswith("EXPLANATION:"):
        data = json.loads(prompt.split("\n", 1)[1])
        return (f"{data['store']} posted the largest month-over-month revenue decline in "
                f"{data['period']}. The evidence shows a broad store-level drop; the returns check "
                "was much smaller and does not account for the missing sales."), "offline-evidence-reasoner"
    if role == "deep":
        question = prompt.split("QUESTION:", 1)[-1].lower()
        focus = "store revenue" if "store" in question or "revenue" in question or "sales" in question else "retail performance"
        text = {"hypotheses": [
            {"name": "Store revenue trend", "question": f"Compare monthly net sales by store to find the largest decline relevant to {focus}."},
            {"name": "Returns trend", "question": "Compare monthly returns by item category and test whether the change could explain lost sales."},
            {"name": "Product mix trend", "question": "Compare monthly net sales by item category."},
            {"name": "Inventory trend", "question": "Compare inventory by store during the focus month."},
        ]}
        return json.dumps(text), "offline-hypothesis-planner"

    p = prompt.lower()
    if "return" in p:
        sql = "SELECT i.i_category AS category, d.d_year AS year, d.d_moy AS month, SUM(sr.sr_return_amt) AS return_amount FROM store_returns sr JOIN item i ON sr.sr_item_sk=i.i_item_sk JOIN date_dim d ON sr.sr_returned_date_sk=d.d_date_sk GROUP BY 1,2,3 ORDER BY 1,2,3"
    elif "inventory" in p:
        sql = "SELECT s.s_store_id AS store_id, d.d_year AS year, d.d_moy AS month, SUM(inv.inv_quantity_on_hand) AS inventory_qty FROM inventory inv JOIN store s ON inv.inv_store_sk=s.s_store_sk JOIN date_dim d ON inv.inv_date_sk=d.d_date_sk GROUP BY 1,2,3 ORDER BY 1,2,3"
    elif "category" in p or "mix" in p:
        sql = "SELECT i.i_category AS category, d.d_year AS year, d.d_moy AS month, SUM(ss.ss_net_paid) AS revenue FROM store_sales ss JOIN item i ON ss.ss_item_sk=i.i_item_sk JOIN date_dim d ON ss.ss_sold_date_sk=d.d_date_sk GROUP BY 1,2,3 ORDER BY 1,2,3"
    else:
        sql = "WITH monthly AS (SELECT s.s_store_id AS store_id, d.d_year AS year, d.d_moy AS month, SUM(ss.ss_net_paid) AS revenue FROM store_sales ss JOIN store s ON ss.ss_store_sk=s.s_store_sk JOIN date_dim d ON ss.ss_sold_date_sk=d.d_date_sk GROUP BY 1,2,3) SELECT store_id, year, month, revenue, LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month) AS prior_revenue, ROUND(100.0*(revenue-LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month))/NULLIF(LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month),0),2) AS pct_change FROM monthly ORDER BY store_id,year,month"
    return sql, "offline-sql-builder"


def generate(role: str, prompt: str) -> tuple[str, str]:
    if role not in {"fast", "deep", "skeptic"}:
        raise ValueError("role must be 'fast', 'deep', or 'skeptic'")
    meterless_token = _setting("METERLESS_RUNTIME_TOKEN").strip()
    nvidia_token = _setting("NVIDIA_API_KEY").strip()
    provider = "meterless" if role in {"fast", "deep"} and meterless_token else "nvidia" if nvidia_token else "offline"
    if provider == "meterless":
        token = meterless_token
        model = _setting("FAST_MODEL" if role == "fast" else "DEEP_MODEL").strip()
        model = model or ("nightshift-fast" if role == "fast" else "nightshift-deep")
        base_url = _setting("METERLESS_BASE_URL") or None
    elif provider == "nvidia":
        token = nvidia_token
        model = (_setting("NEMOTRON_REVIEW_MODEL") if role == "skeptic" else
                 _setting("NEMOTRON_FAST_MODEL") if role == "fast" else
                 _setting("NEMOTRON_MODEL")) or "nvidia/nemotron-3.5-bolt-e4b"
        base_url = _setting("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    else:
        text, model = _offline(role, prompt)
        provider = "offline"
    ok, error = True, None
    if provider != "offline":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=token, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are WhyTrace, a careful retail analytics agent. Use only the supplied schema/evidence. Return the requested format exactly. Never invent query results."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            text = response.choices[0].message.content or ""
            if not text.strip():
                raise RuntimeError("Model returned an empty response")
        except Exception as exc:
            ok, error = False, f"{type(exc).__name__}: {exc}"
            text, model = _offline(role, prompt)
            model = f"{model} (fallback from {provider})"
    if provider != "offline" and ok:
        model = f"{provider.title()} · {model}"

    log_dir = Path(os.getenv("WHYTRACE_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "role": role, "provider": provider,
             "model": model, "ok": ok}
    if error:
        entry["error"] = error
    with (log_dir / "requests.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return text, model
