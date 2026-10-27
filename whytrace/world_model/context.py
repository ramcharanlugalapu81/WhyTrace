from __future__ import annotations

from whytrace.world_model.store import WorldStoreService


class ContextBuilderService:
    def __init__(self, store: WorldStoreService | None = None):
        self.store = store or WorldStoreService()

    def build_context(self, evidence_ids: list[str]) -> dict:
        evidence = [row for eid in evidence_ids if (row := self.store.get(eid))]
        provenance = [{"evidence_id": row["evidence_id"], "sql": row["sql"],
                       "source": row["source"], "model": row["model"]} for row in evidence]
        return {"evidence": evidence, "provenance": provenance}
