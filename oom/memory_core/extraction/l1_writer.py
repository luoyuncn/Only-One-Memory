from __future__ import annotations

from oom.memory_core.embeddings.base import EmbeddingService
from oom.memory_core.extraction.l1_dedup import DedupDecision
from oom.memory_core.stores.base import MemoryStore
from oom.memory_core.types import MemoryAtom


class L1Writer:
    def __init__(self, store: MemoryStore, embedding_service: EmbeddingService | None = None) -> None:
        self.store = store
        self.embedding_service = embedding_service

    async def write_batch(
        self, memories: list[MemoryAtom], decisions: list[DedupDecision] | None = None
    ) -> int:
        allowed = None if decisions is None else {decision.memory_id for decision in decisions if decision.action in {"store", "merge"}}
        count = 0
        for memory in memories:
            if allowed is not None and memory.id not in allowed:
                continue
            embedding = await self.embedding_service.embed(memory.content) if self.embedding_service is not None else None
            await self.store.upsert_l1(memory, embedding=embedding)
            count += 1
        return count
