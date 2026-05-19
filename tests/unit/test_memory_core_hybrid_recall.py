from datetime import datetime, timezone

from oom.memory_core.config import AppConfig
from oom.memory_core.core import MemoryCore
from oom.memory_core.types import MemoryAtom, MemorySearchRequest, MemorySearchHit, StoreCapabilities


def _memory(memory_id: str, content: str) -> MemoryAtom:
    now = datetime(2026, 5, 19, tzinfo=timezone.utc)
    return MemoryAtom(
        id=memory_id,
        tenant_id="default",
        user_id="u1",
        agent_id="a1",
        session_id="s1",
        session_key="agent:u1:s1",
        content=content,
        type="episodic",
        priority=80,
        confidence=0.8,
        created_at=now,
        updated_at=now,
    )


class HybridStore:
    def __init__(self) -> None:
        self.memories = {
            "a": _memory("a", "关键词命中"),
            "b": _memory("b", "关键词和向量都命中"),
            "c": _memory("c", "语义命中"),
        }

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def capabilities(self) -> StoreCapabilities:
        return StoreCapabilities(backend="test", fts_search=True, vector_search=True, vector_backend="fake")

    async def search_l1_fts(self, query, limit, filters=None):
        return [MemorySearchHit(memory=self.memories["a"], score=1.0), MemorySearchHit(memory=self.memories["b"], score=0.5)]

    async def search_l1_vector(self, embedding, limit, filters=None):
        return [MemorySearchHit(memory=self.memories["b"], score=1.0), MemorySearchHit(memory=self.memories["c"], score=0.5)]


async def test_search_memories_uses_rrf_to_boost_overlapping_hits():
    core = MemoryCore(AppConfig(), store=HybridStore())

    result = await core.search_memories(
        MemorySearchRequest(
            tenant_id="default",
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            session_key="agent:u1:s1",
            query="Only-One-Memory",
            limit=3,
        )
    )

    assert result.hits[0].memory.id == "b"
