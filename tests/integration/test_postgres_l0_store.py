import os
from datetime import datetime, timezone

import pytest

from oom.memory_core.config import PostgresConfig
from oom.memory_core.stores.postgres_store import PostgresMemoryStore
from oom.memory_core.types import L0Event


pytestmark = pytest.mark.skipif(
    not os.getenv("OOM_POSTGRES_DSN"),
    reason="OOM_POSTGRES_DSN is required for Postgres integration tests",
)


async def test_postgres_l0_upsert_and_fts_search():
    store = PostgresMemoryStore(PostgresConfig(dsn=os.environ["OOM_POSTGRES_DSN"]))
    await store.init()
    event = L0Event(
        id="evt_pg_1",
        tenant_id="default",
        user_id="u1",
        agent_id="a1",
        session_id="s1",
        session_key="agent:u1:s1",
        role="user",
        content="用户需要 Postgres pgvector 作为一期能力",
        event_ts=datetime(2026, 5, 19, tzinfo=timezone.utc),
        recorded_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )

    assert await store.upsert_l0(event, embedding=[0.1, 0.2, 0.3]) is True
    hits = await store.search_l0_fts("Postgres pgvector", limit=5, filters={})

    assert len(hits) >= 1
    await store.close()
