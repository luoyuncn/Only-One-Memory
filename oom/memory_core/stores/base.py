from __future__ import annotations

from typing import Any, Protocol

from oom.memory_core.types import (
    ConversationSearchHit,
    L0Event,
    MemoryAtom,
    MemorySearchHit,
    ProfileDocument,
    SceneBlock,
    StoreCapabilities,
)
from oom.memory_core.offload.types import OffloadEntry


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

    async def reindex_all(self) -> dict[str, int | None]: ...

    async def list_scenes(self, tenant_id: str, user_id: str) -> list[SceneBlock]: ...

    async def get_scene(self, scene_id: str, tenant_id: str) -> SceneBlock | None: ...

    async def upsert_scene(self, scene: SceneBlock) -> SceneBlock: ...

    async def get_profile(self, tenant_id: str, scope: str, scope_id: str) -> ProfileDocument | None: ...

    async def upsert_profile(self, profile: ProfileDocument) -> ProfileDocument: ...

    async def upsert_offload_entry(self, entry: OffloadEntry) -> OffloadEntry: ...

    async def list_offload_entries(self, tenant_id: str, session_id: str) -> list[OffloadEntry]: ...
