from datetime import datetime, timezone

from only_one_memory.memory_core.config import StoreConfig
from only_one_memory.memory_core.stores.sqlite_store import SqliteMemoryStore
from only_one_memory.memory_core.types import L0Event


async def test_sqlite_l0_upsert_and_fts_search(tmp_path):
    store = SqliteMemoryStore(StoreConfig().sqlite.model_copy(update={"path": str(tmp_path / "memory.db")}))
    await store.init()
    event = L0Event(
        id="evt1",
        tenant_id="default",
        user_id="u1",
        agent_id="a1",
        session_id="s1",
        session_key="agent:u1:s1",
        role="user",
        content="用户正在设计 Agent 记忆系统",
        event_ts=datetime(2026, 5, 19, tzinfo=timezone.utc),
        recorded_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )

    assert await store.upsert_l0(event, embedding=[0.1, 0.2, 0.3]) is True
    hits = await store.search_l0_fts("Agent 记忆", limit=5, filters={})

    assert len(hits) == 1
    assert hits[0].event.id == "evt1"
    await store.close()
