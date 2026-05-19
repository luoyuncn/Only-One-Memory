from __future__ import annotations

import uuid
from datetime import datetime, timezone

from only_one_memory.memory_core.capture.idempotency import IdempotencyCache, request_hash
from only_one_memory.memory_core.capture.sanitizer import sanitize_messages
from only_one_memory.memory_core.config import AppConfig
from only_one_memory.memory_core.stores.base import MemoryStore
from only_one_memory.memory_core.stores.factory import create_store
from only_one_memory.memory_core.types import (
    CaptureResult,
    CaptureTurnRequest,
    ConversationSearchRequest,
    ConversationSearchResult,
    L0Event,
)


class MemoryCore:
    def __init__(self, config: AppConfig, store: MemoryStore | None = None) -> None:
        self.config = config
        self.store = store or create_store(config.store)
        self._initialized = False
        self._idempotency = IdempotencyCache()

    async def initialize(self) -> None:
        if not self._initialized:
            await self.store.init()
            self._initialized = True

    async def close(self) -> None:
        if self._initialized:
            await self.store.close()
            self._initialized = False

    async def commit_turn(self, request: CaptureTurnRequest) -> CaptureResult:
        await self.initialize()
        digest = request_hash(request)
        cached = self._idempotency.get(request.idempotency_key, digest)
        if cached is not None:
            return cached

        recorded_at = datetime.now(timezone.utc)
        event_ids = []
        for index, message in enumerate(sanitize_messages(request.messages)):
            event_id = self._event_id(request, index)
            event = L0Event(
                id=event_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                agent_id=request.agent_id,
                session_id=request.session_id,
                session_key=request.session_key,
                role=message.role,
                content=message.content,
                event_ts=message.timestamp,
                recorded_at=recorded_at,
                metadata={**request.metadata, **message.metadata},
            )
            await self.store.upsert_l0(event, embedding=self._embedding_for(message.content))
            event_ids.append(event_id)

        result = CaptureResult(
            l0_recorded_count=len(event_ids),
            event_ids=event_ids,
            idempotency_key=request.idempotency_key,
        )
        self._idempotency.put(request.idempotency_key, digest, result)
        return result

    async def search_conversations(self, request: ConversationSearchRequest) -> ConversationSearchResult:
        await self.initialize()
        filters = {
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "agent_id": request.agent_id,
            "session_id": request.session_id,
            "session_key": request.session_key,
        }
        hits = await self.store.search_l0_fts(request.query, limit=request.limit, filters=filters)
        return ConversationSearchResult(total=len(hits), hits=hits)

    @staticmethod
    def _event_id(request: CaptureTurnRequest, index: int) -> str:
        raw = f"{request.tenant_id}:{request.session_key}:{request.idempotency_key}:{index}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))

    @staticmethod
    def _embedding_for(content: str) -> list[float]:
        length = float(len(content))
        checksum = float(sum(ord(char) for char in content) % 997)
        return [length, checksum, 1.0]
