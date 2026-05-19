import asyncpg
import pytest

from oom.app.main import CREATED_APPS
from oom.memory_core.config import AppConfig


@pytest.fixture(autouse=True)
async def reset_postgres_when_configured():
    config = AppConfig()
    if config.store.backend != "postgres" or not config.store.postgres.dsn:
        yield
        return
    conn = await asyncpg.connect(config.store.postgres.dsn.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        tables = [
            "audit_logs",
            "offload_entries",
            "profiles",
            "scenes",
            "memory_sources",
            "memories",
            "conversation_events",
            "pipeline_jobs",
        ]
        existing = [
            table
            for table in tables
            if await conn.fetchval("SELECT to_regclass($1)", f"public.{table}") is not None
        ]
        if existing:
            quoted = ", ".join(f'"{table}"' for table in existing)
            await conn.execute(f"TRUNCATE TABLE {quoted} CASCADE")
    finally:
        await conn.close()
    yield


@pytest.fixture(autouse=True)
async def close_created_apps():
    yield
    for app in list(CREATED_APPS):
        core = getattr(app.state, "memory_core", None)
        if core is not None:
            await core.close()
        CREATED_APPS.discard(app)
