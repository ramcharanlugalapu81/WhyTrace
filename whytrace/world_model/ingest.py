from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from whytrace.world_model.store import WorldStoreService


class IngestPipelineService:
    def __init__(self, store: WorldStoreService | None = None, log_path: str | Path | None = None):
        self.store = store or WorldStoreService()
        self.log_path = Path(log_path or os.getenv("WHYTRACE_LOG_DIR", "logs")) / "ingest.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def ingest(self, query_result: dict) -> dict:
        record = self.store.upsert({
            "sql": query_result["sql"], "params": query_result.get("params", []),
            "rows": query_result.get("rows", []), "source": query_result.get("source", "zetaris"),
            "model": query_result.get("model", "unknown"),
        })
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                                "evidence_id": record["evidence_id"], "row_count": record["row_count"]}) + "\n")
        return record
