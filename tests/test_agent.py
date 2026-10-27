import json

from whytrace.agent import run_agent
from whytrace.world_model.store import WorldStoreService


def offline(role, prompt):
    if role == "deep":
        if prompt.startswith("EXPLANATION:"):
            from whytrace.llm import _offline
            return _offline(role, prompt)
        return json.dumps({"hypotheses": [
            {"name": "Store revenue changed", "question": "Compare monthly net sales by store"},
            {"name": "Returns spike", "question": "Compare monthly return amount by item category"},
            {"name": "Product mix shifted", "question": "Compare monthly sales by item category"},
            {"name": "Inventory trend", "question": "Compare inventory by store"},
        ]}), "test-deep"
    from whytrace.llm import _offline
    return _offline(role, prompt)


def test_planted_cause_ranks_first_and_decoy_ruled_out(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("WHYTRACE_LOG_DIR", str(tmp_path))
    report = run_agent("Why did S3 revenue drop in March 2026?",
                       store=WorldStoreService(tmp_path / "evidence.jsonl"),
                       generator=offline, trace_path=tmp_path / "trace.jsonl")
    assert report["ranked_drivers"][0]["title"].startswith("S3 revenue")
    assert report["ranked_drivers"][0]["verified"] is True
    assert any("returns" in x["title"].lower() for x in report["ruled_out"])
    assert any("Electronics" in x["claim"] for x in report["ruled_out"])
    assert report["agent_mode"] == "Offline evidence agent"
    assert report["skeptic_review"]["model"] == "offline-skeptic"
    assert report["context"]["provenance"][0]["source"] == "duckdb"
    by_name = {step["name"]: step["rows"] for step in report["hypotheses"]}
    assert "return_amount" in by_name["Returns spike"][0]
    assert "revenue" in by_name["Product mix shifted"][0]
    assert "inventory_qty" in by_name["Inventory trend"][0]


def test_verifier_flags_tampered_number(tmp_path):
    from whytrace.verifier import verify_claim
    from whytrace.sample_data import get_connection
    con = get_connection()
    query = lambda sql, params=None: [dict(zip([d[0] for d in con.execute(sql).description], r)) for r in con.execute(sql, params or []).fetchall()]
    store = WorldStoreService(tmp_path / "evidence.jsonl")
    evidence = store.upsert({"sql": "SELECT 10 AS amount", "rows": [{"amount": 10}]})
    claim = {"numeric_claims": [{"evidence_id": evidence["evidence_id"], "row_index": 0,
                                 "column": "amount", "value": 999}]}
    assert verify_claim(claim, store, query)["verified"] is False


def test_supported_returns_question_uses_returns_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("WHYTRACE_LOG_DIR", str(tmp_path))
    report = run_agent("How did Electronics returns change in March 2026?",
                       store=WorldStoreService(tmp_path / "returns.jsonl"),
                       generator=offline, trace_path=tmp_path / "returns-trace.jsonl")
    lead = report["ranked_drivers"][0]
    assert "electronics returns" in lead["title"].lower()
    assert lead["verified"] is True
    assert lead["evidence_ids"] == [next(p["evidence_id"] for p in report["context"]["provenance"] if "store_returns" in p["sql"])]


def test_supported_category_question_uses_sales_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("WHYTRACE_LOG_DIR", str(tmp_path))
    report = run_agent("Which product category had the largest revenue decline in March 2026?",
                       store=WorldStoreService(tmp_path / "category.jsonl"),
                       generator=offline, trace_path=tmp_path / "category-trace.jsonl")
    lead = report["ranked_drivers"][0]
    assert "category revenue" in lead["claim"]
    assert lead["verified"] is True


def test_supported_inventory_question_uses_inventory_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("WHYTRACE_LOG_DIR", str(tmp_path))
    report = run_agent("How did average inventory change in March 2026?",
                       store=WorldStoreService(tmp_path / "inventory.jsonl"),
                       generator=offline, trace_path=tmp_path / "inventory-trace.jsonl")
    lead = report["ranked_drivers"][0]
    assert "inventory" in lead["title"].lower()
    assert lead["verified"] is True
