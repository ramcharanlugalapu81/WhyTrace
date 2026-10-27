from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path


class WorldStoreService:
    """Atomic JSONL evidence store; stable SQL+params hashes make writes idempotent."""
    _lock = threading.RLock()

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("WHYTRACE_EVIDENCE_PATH", "logs/evidence.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def evidence_id(sql: str, params=None) -> str:
        raw = json.dumps({"sql": sql.strip(), "params": params or []}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def get(self, evidence_id: str) -> dict | None:
        return next((r for r in self.all() if r["evidence_id"] == evidence_id), None)

    def upsert(self, evidence: dict) -> dict:
        record = dict(evidence)
        record["evidence_id"] = self.evidence_id(record["sql"], record.get("params"))
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        record.setdefault("source", "zetaris")
        record.setdefault("model", "unknown")
        record["row_count"] = len(record.get("rows", []))
        with self._lock:
            records = self.all()
            existing = next((i for i, r in enumerate(records) if r["evidence_id"] == record["evidence_id"]), None)
            if existing is None:
                records.append(record)
                self._atomic_write(records)
            else:
                previous = records[existing]
                comparable = ("sql", "params", "rows", "row_count", "source", "model")
                if any(previous.get(key) != record.get(key) for key in comparable):
                    records[existing] = record
                    self._atomic_write(records)
        return self.get(record["evidence_id"])

    def _atomic_write(self, records: list[dict]) -> None:
        payload = "".join(json.dumps(r, default=str, sort_keys=True) + "\n" for r in records)
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
