import os
from datetime import datetime, timezone

import pytest

from oom.memory_core.config import PostgresConfig, StoreConfig
from oom.memory_core.stores.postgres_store import PostgresMemoryStore
from oom.memory_core.stores.sqlite_store import SqliteMemoryStore
from oom.memory_core.types import MemoryAtom


async def assert_l1_store_contract(store):
    await store.init()
    memory = MemoryAtom(
        id="mem1",
        tenant_id="default",
        user_id="u1",
        agent_id="a1",
        session_id="s1",
        session_key="agent:u1:s1",
        content="用户正在开发 Python Agent Memory Runtime",
        type="episodic",
        priority=90,
        confidence=0.9,
        scene_name="我在和用户做Agent记忆系统",
        source_event_ids=["evt1"],
        timestamps=["2026-05-19T00:00:00Z"],
        metadata={},
        created_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )

    assert await store.upsert_l1(memory, embedding=[0.1, 0.2, 0.3]) is True
    hits = await store.search_l1_fts("Python Agent Memory", limit=5, filters={"tenant_id": "default"})

    assert any(hit.memory.id == "mem1" for hit in hits)
    await store.close()


async def test_sqlite_l1_store_contract(tmp_path):
    store = SqliteMemoryStore(StoreConfig().sqlite.model_copy(update={"path": str(tmp_path / "memory.db")}))

    await assert_l1_store_contract(store)


@pytest.mark.skipif(not os.getenv("OOM_POSTGRES_DSN"), reason="OOM_POSTGRES_DSN is required for Postgres tests")
async def test_postgres_l1_store_contract():
    store = PostgresMemoryStore(PostgresConfig(dsn=os.environ["OOM_POSTGRES_DSN"]))

    await assert_l1_store_contract(store)
