from __future__ import annotations

from typing import Any, Protocol

from oom.memory_core.types import ConversationSearchHit, L0Event, MemoryAtom, MemorySearchHit, StoreCapabilities


class MemoryStore(Protocol):
    async def init(self) -> None: ...

    async def close(self) -> None: ...

    def capabilities(self) -> StoreCapabilities: ...

    async def upsert_l0(self, event: L0Event, embedding: list[float] | None = None) -> bool: ...

    async def search_l0_fts(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[ConversationSearchHit]: ...

    async def search_l0_vector(
        self, embedding: list[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[ConversationSearchHit]: ...

    async def query_l0_for_l1(self, filters: dict[str, Any] | None = None, limit: int = 100) -> list[L0Event]: ...

    async def upsert_l1(self, memory: MemoryAtom, embedding: list[float] | None = None) -> bool: ...

    async def search_l1_fts(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[MemorySearchHit]: ...

    async def search_l1_vector(
        self, embedding: list[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[MemorySearchHit]: ...
