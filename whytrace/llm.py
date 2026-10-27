"""Single injectable model gateway with a deterministic offline path."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
LOG_DIR = Path(os.getenv("WHYTRACE_LOG_DIR", "logs"))


def _sample_mode() -> bool:
    return os.getenv("SAMPLE_MODE", "true").lower() in {"1", "true", "yes", "on"}


def _offline(role: str, prompt: str) -> tuple[str, str]:
    if role == "deep":
        text = json.dumps({"hypotheses": [
            {"name": "Store revenue changed", "question": "Compare monthly net sales by store; identify the largest month-over-month decline."},
            {"name": "Product mix shifted", "question": "Compare monthly sales by item category."},
            {"name": "Returns spike", "question": "Compare monthly return amount by item category."},
            {"name": "Inventory constraint", "question": "Compare March inventory by store."},
        ]})
    else:
        p = prompt.lower()
        if "monthly net sales by store" in p or "store revenue" in p:
            sql = "WITH monthly AS (SELECT s.s_store_id AS store_id, d.d_year AS year, d.d_moy AS month, SUM(ss.ss_net_paid) AS revenue FROM store_sales ss JOIN store s ON ss.ss_store_sk=s.s_store_sk JOIN date_dim d ON ss.ss_sold_date_sk=d.d_date_sk GROUP BY 1,2,3) SELECT store_id, year, month, revenue, LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month) AS prior_revenue, ROUND(100.0*(revenue-LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month))/NULLIF(LAG(revenue) OVER (PARTITION BY store_id ORDER BY year,month),0),2) AS pct_change FROM monthly ORDER BY store_id,year,month"
        elif "return" in p:
            sql = "SELECT i.i_category AS category, d.d_year AS year, d.d_moy AS month, SUM(sr.sr_return_amt) AS return_amount FROM store_returns sr JOIN item i ON sr.sr_item_sk=i.i_item_sk JOIN date_dim d ON sr.sr_returned_date_sk=d.d_date_sk GROUP BY 1,2,3 ORDER BY 1,2,3"
        elif "inventory" in p:
            sql = "SELECT s.s_store_id AS store_id, SUM(inv.inv_quantity_on_hand) AS inventory_qty FROM inventory inv JOIN store s ON inv.inv_store_sk=s.s_store_sk JOIN date_dim d ON inv.inv_date_sk=d.d_date_sk WHERE d.d_year=2026 AND d.d_moy=3 GROUP BY 1 ORDER BY 1"
        else:
            sql = "SELECT i.i_category AS category, d.d_year AS year, d.d_moy AS month, SUM(ss.ss_net_paid) AS revenue FROM store_sales ss JOIN item i ON ss.ss_item_sk=i.i_item_sk JOIN date_dim d ON ss.ss_sold_date_sk=d.d_date_sk GROUP BY 1,2,3 ORDER BY 1,2,3"
        text = sql
    return text, "offline-template"


def generate(role: str, prompt: str) -> tuple[str, str]:
    if role not in {"fast", "deep"}:
        raise ValueError("role must be 'fast' or 'deep'")
    model = os.getenv("FAST_MODEL" if role == "fast" else "DEEP_MODEL", "") or "offline-template"
    token, base = os.getenv("METERLESS_RUNTIME_TOKEN"), os.getenv("METERLESS_BASE_URL")
    ok = True
    if not token or _sample_mode():
        text, model = _offline(role, prompt)
    else:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=token, base_url=base or None)
            response = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], temperature=0,
            )
            text = response.choices[0].message.content or ""
        except Exception as exc:
            ok = False
            text = ""
            err = str(exc)
        else:
            err = None
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "role": role, "model": model, "ok": ok}
    if not ok:
        entry["error"] = err
    with (LOG_DIR / "requests.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return text, model
