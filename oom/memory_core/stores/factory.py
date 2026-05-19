"""根据配置创建 SQLite 或 Postgres store。"""

from __future__ import annotations

from oom.memory_core.config import StoreConfig
from oom.memory_core.stores.base import MemoryStore
from oom.memory_core.stores.postgres_store import PostgresMemoryStore
from oom.memory_core.stores.sqlite_store import SqliteMemoryStore


def create_store(config: StoreConfig) -> MemoryStore:
    if config.backend == "sqlite":
        return SqliteMemoryStore(config.sqlite)
    if config.backend == "postgres":
        return PostgresMemoryStore(config.postgres)
    raise ValueError(f"Unsupported memory store backend: {config.backend}")
