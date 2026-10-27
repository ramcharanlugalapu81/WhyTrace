import json

from whytrace.world_model.context import ContextBuilderService
from whytrace.world_model.ingest import IngestPipelineService
from whytrace.world_model.store import WorldStoreService


def test_idempotent_ingest(tmp_path):
    store = WorldStoreService(tmp_path / "evidence.jsonl")
    ingest = IngestPipelineService(store, tmp_path)
    a = ingest.ingest({"sql": "SELECT 1 AS n", "rows": [{"n": 1}], "model": "test"})
    b = ingest.ingest({"sql": "SELECT 1 AS n", "rows": [{"n": 1}], "model": "test"})
    assert a["evidence_id"] == b["evidence_id"]
    assert len(store.all()) == 1


def test_claim_resolves_to_source_query(tmp_path):
    store = WorldStoreService(tmp_path / "evidence.jsonl")
    record = store.upsert({"sql": "SELECT 42 AS answer", "rows": [{"answer": 42}]})
    claim = {"evidence_ids": [record["evidence_id"]]}
    source = store.get(claim["evidence_ids"][0])
    assert source["sql"] == "SELECT 42 AS answer"
    assert source["source"] == "zetaris"


def test_crash_resume_leaves_no_corruption(tmp_path):
    path = tmp_path / "evidence.jsonl"
    store = WorldStoreService(path)
    store.upsert({"sql": "SELECT 1", "rows": [{"x": 1}]})
    # A partial temporary checkpoint from an interrupted write is ignored; next
    # atomic upsert rewrites a valid complete JSONL file.
    (tmp_path / "evidence.jsonl.interrupted.tmp").write_text('{"truncated":', encoding="utf-8")
    store.upsert({"sql": "SELECT 2", "rows": [{"x": 2}]})
    assert len(store.all()) == 2
    assert all("evidence_id" in json.loads(line) for line in path.read_text().splitlines())


def test_context_payload_shape(tmp_path):
    store = WorldStoreService(tmp_path / "evidence.jsonl")
    row = store.upsert({"sql": "SELECT 1", "rows": [{"x": 1}], "model": "m"})
    payload = ContextBuilderService(store).build_context([row["evidence_id"]])
    assert set(payload) == {"evidence", "provenance"}
    assert payload["evidence"][0]["evidence_id"] == row["evidence_id"]
    assert payload["provenance"][0]["sql"] == "SELECT 1"
