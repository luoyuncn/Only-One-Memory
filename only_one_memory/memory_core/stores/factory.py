from __future__ import annotations

from only_one_memory.memory_core.config import StoreConfig
from only_one_memory.memory_core.stores.base import MemoryStore
from only_one_memory.memory_core.stores.postgres_store import PostgresMemoryStore
from only_one_memory.memory_core.stores.sqlite_store import SqliteMemoryStore


def create_store(config: StoreConfig) -> MemoryStore:
    if config.backend == "sqlite":
        return SqliteMemoryStore(config.sqlite)
    if config.backend == "postgres":
        return PostgresMemoryStore(config.postgres)
    raise ValueError(f"Unsupported memory store backend: {config.backend}")
