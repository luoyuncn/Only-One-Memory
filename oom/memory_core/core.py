from __future__ import annotations

import uuid
from datetime import datetime, timezone

from oom.memory_core.capture.idempotency import IdempotencyCache, request_hash
from oom.memory_core.capture.sanitizer import sanitize_messages
from oom.memory_core.config import AppConfig
from oom.memory_core.observability.metrics import increment
from oom.memory_core.offload.types import OffloadEntry
from oom.memory_core.pipeline.checkpoint import CheckpointStore
from oom.memory_core.pipeline.manager import PipelineManager
from oom.memory_core.recall.auto_recall import build_dynamic_context
from oom.memory_core.recall.rrf import rrf_merge
from oom.memory_core.stores.base import MemoryStore
from oom.memory_core.stores.factory import create_store
from oom.memory_core.types import (
    CaptureResult,
    CaptureTurnRequest,
    ConversationSearchRequest,
    ConversationSearchResult,
    L0Event,
    MemorySearchRequest,
    MemorySearchResult,
    ProfileDocument,
    ProfilePatchRequest,
    RecallBeforeRequest,
    RecallBeforeResult,
    SceneBlock,
    SceneListResult,
    ScenePatchRequest,
)


class MemoryCore:
    def __init__(self, config: AppConfig, store: MemoryStore | None = None) -> None:
        self.config = config
        self.store = store or create_store(config.store)
        self._initialized = False
        self._idempotency = IdempotencyCache()
        self.pipeline = PipelineManager(
            every_n_conversations=config.pipeline.every_n_conversations,
            enable_warmup=config.pipeline.enable_warmup,
            idle_timeout_seconds=config.pipeline.idle_timeout_seconds,
        )
        self._checkpoint_store = CheckpointStore(config.pipeline.checkpoint_path) if config.pipeline.checkpoint_path else None

    async def initialize(self) -> None:
        if not self._initialized:
            await self.store.init()
            if self._checkpoint_store is not None:
                self.pipeline.load_states(await self._checkpoint_store.load())
            self._initialized = True

    async def close(self) -> None:
        if self._initialized:
            if self._checkpoint_store is not None:
                await self._checkpoint_store.save(self.pipeline.dump_states())
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
        await self.pipeline.notify_conversation(request.session_key)
        increment("oom_capture_total")
        return result

    async def search_conversations(self, request: ConversationSearchRequest) -> ConversationSearchResult:
        await self.initialize()
        increment("oom_search_total")
        filters = {
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "agent_id": request.agent_id,
            "session_id": request.session_id,
            "session_key": request.session_key,
        }
        hits = await self.store.search_l0_fts(request.query, limit=request.limit, filters=filters)
        return ConversationSearchResult(total=len(hits), hits=hits)

    async def search_memories(self, request: MemorySearchRequest) -> MemorySearchResult:
        await self.initialize()
        increment("oom_search_total")
        filters = {
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "agent_id": request.agent_id,
            "session_id": request.session_id,
            "session_key": request.session_key,
        }
        hits = await self._search_l1_hybrid(request.query, request.limit, filters)
        return MemorySearchResult(total=len(hits), hits=hits)

    async def before_recall(self, request: RecallBeforeRequest) -> RecallBeforeResult:
        await self.initialize()
        increment("oom_recall_total")
        memory_request = MemorySearchRequest(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            session_key=request.session_key,
            query=request.user_text,
            limit=request.max_results,
        )
        conversation_request = ConversationSearchRequest(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            session_key=request.session_key,
            query=request.user_text,
            limit=request.max_results,
        )
        memory_hits = (await self.search_memories(memory_request)).hits
        conversation_hits = (await self.search_conversations(conversation_request)).hits
        return RecallBeforeResult(
            dynamic_context=build_dynamic_context(memory_hits, conversation_hits),
            memory_hits=memory_hits,
            conversation_hits=conversation_hits,
        )

    def pipeline_status(self) -> dict[str, object]:
        return self.pipeline.status()

    async def reindex_all(self) -> dict[str, object]:
        await self.initialize()
        reindex = getattr(self.store, "reindex_all", None)
        if reindex is None:
            return {"l0": None, "l1": None, "l2": None, "l3": None}
        return await reindex()

    async def list_scenes(self, tenant_id: str, user_id: str) -> SceneListResult:
        await self.initialize()
        return SceneListResult(items=await self.store.list_scenes(tenant_id, user_id))

    async def get_scene(self, scene_id: str, tenant_id: str) -> SceneBlock | None:
        await self.initialize()
        return await self.store.get_scene(scene_id, tenant_id)

    async def patch_scene(self, scene_id: str, request: ScenePatchRequest) -> SceneBlock:
        await self.initialize()
        scene = SceneBlock(
            id=scene_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            filename=f"{scene_id}.md",
            content=request.content,
            summary=request.summary,
            heat=request.heat,
            metadata=request.metadata,
            updated_at=datetime.now(timezone.utc),
        )
        return await self.store.upsert_scene(scene)

    async def get_profile(self, tenant_id: str, scope: str, scope_id: str) -> ProfileDocument | None:
        await self.initialize()
        return await self.store.get_profile(tenant_id, scope, scope_id)

    async def patch_profile(self, scope: str, scope_id: str, request: ProfilePatchRequest) -> ProfileDocument:
        await self.initialize()
        profile = ProfileDocument(
            tenant_id=request.tenant_id,
            scope=scope,
            scope_id=scope_id,
            content=request.content,
            metadata=request.metadata,
            updated_at=datetime.now(timezone.utc),
        )
        return await self.store.upsert_profile(profile)

    async def upsert_offload_entry(self, entry: OffloadEntry) -> OffloadEntry:
        await self.initialize()
        return await self.store.upsert_offload_entry(entry)

    async def list_offload_entries(self, tenant_id: str, session_id: str) -> list[OffloadEntry]:
        await self.initialize()
        return await self.store.list_offload_entries(tenant_id, session_id)

    @staticmethod
    def _event_id(request: CaptureTurnRequest, index: int) -> str:
        raw = f"{request.tenant_id}:{request.session_key}:{request.idempotency_key}:{index}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))

    @staticmethod
    def _embedding_for(content: str) -> list[float]:
        length = float(len(content))
        checksum = float(sum(ord(char) for char in content) % 997)
        return [length, checksum, 1.0]

    async def _search_l1_hybrid(
        self, query: str, limit: int, filters: dict[str, str | None]
    ) -> list:
        capabilities = self.store.capabilities()
        fts_hits = await self.store.search_l1_fts(query, limit=limit, filters=filters)
        if not capabilities.vector_search:
            return fts_hits

        vector_hits = await self.store.search_l1_vector(self._embedding_for(query), limit=limit, filters=filters)
        hits_by_id = {hit.memory.id: hit for hit in [*fts_hits, *vector_hits]}
        merged = rrf_merge(
            [[hit.memory.id for hit in fts_hits], [hit.memory.id for hit in vector_hits]],
            limit=limit,
        )
        return [hits_by_id[hit.id].model_copy(update={"score": hit.score}) for hit in merged]
