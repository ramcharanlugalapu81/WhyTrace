"""Re-execute cited SQL and verify numeric values attached to report claims."""
from __future__ import annotations

from whytrace.zetaris_client import run_query


def verify_claim(claim: dict, store, query_fn=run_query, tolerance: float = 0.005) -> dict:
    checks = []
    for metric in claim.get("numeric_claims", []):
        evidence = store.get(metric["evidence_id"])
        ok, actual = False, None
        if evidence:
            try:
                rows = query_fn(evidence["sql"], evidence.get("params", []))
                row_idx = int(metric.get("row_index", 0))
                actual = rows[row_idx].get(metric["column"])
                expected = float(metric["value"])
                actual_f = float(actual)
                ok = abs(actual_f - expected) <= max(abs(expected) * tolerance, 1e-9)
            except (IndexError, KeyError, TypeError, ValueError):
                ok = False
        checks.append({**metric, "actual": actual, "verified": ok})
    claim["verified"] = all(c["verified"] for c in checks)
    claim["verification"] = checks
    return claim


def verify_report(report: dict, store, query_fn=run_query) -> dict:
    for claim in report.get("ranked_drivers", []) + report.get("ruled_out", []):
        verify_claim(claim, store, query_fn)
    return report
