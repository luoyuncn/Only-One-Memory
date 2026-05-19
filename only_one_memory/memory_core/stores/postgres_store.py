from __future__ import annotations

from typing import Any

from only_one_memory.memory_core.config import PostgresConfig
from only_one_memory.memory_core.types import ConversationSearchHit, L0Event, StoreCapabilities


class PostgresMemoryStore:
    def __init__(self, config: PostgresConfig) -> None:
        self.config = config

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def capabilities(self) -> StoreCapabilities:
        return StoreCapabilities(
            backend="postgres",
            fts_search=True,
            vector_search=True,
            vector_backend="pgvector",
        )

    async def upsert_l0(self, event: L0Event, embedding: list[float] | None = None) -> bool:
        raise NotImplementedError

    async def search_l0_fts(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[ConversationSearchHit]:
        raise NotImplementedError

    async def search_l0_vector(
        self, embedding: list[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[ConversationSearchHit]:
        raise NotImplementedError

    async def query_l0_for_l1(self, filters: dict[str, Any] | None = None, limit: int = 100) -> list[L0Event]:
        raise NotImplementedError
