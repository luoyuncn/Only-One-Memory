"""MemoryCore 是业务入口，串联采集、检索、召回、场景、画像和管线。"""

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
    MemoryAtom,
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
    """唯一稳定业务入口。

    外层 HTTP、worker 或未来 SDK 都应通过这里访问记忆能力；这样 API 协议、
    后台任务和存储实现可以独立演进，而不会把业务规则散落在路由里。
    """

    def __init__(self, config: AppConfig, store: MemoryStore | None = None) -> None:
        self.config = config
        self.store = store or create_store(config.store)
        self._initialized = False
        self._idempotency = IdempotencyCache()
        self.pipeline = PipelineManager(
            every_n_conversations=config.pipeline.every_n_conversations,
            enable_warmup=config.pipeline.enable_warmup,
            idle_timeout_seconds=config.pipeline.idle_timeout_seconds,
            l1_runner=self._run_l1_for_session,
        )
        self._checkpoint_store = CheckpointStore(config.pipeline.checkpoint_path) if config.pipeline.checkpoint_path else None

    async def initialize(self) -> None:
        """懒初始化 store 和 checkpoint，避免测试/导入模块时立即打开连接。"""
        if not self._initialized:
            await self.store.init()
            if self._checkpoint_store is not None:
                self.pipeline.load_states(await self._checkpoint_store.load())
            self._initialized = True

    async def close(self) -> None:
        """关闭前保存 pipeline 状态，保证进程重启后能继续按 session 推进。"""
        if self._initialized:
            if self._checkpoint_store is not None:
                await self._checkpoint_store.save(self.pipeline.dump_states())
            await self.store.close()
            self._initialized = False

    async def commit_turn(self, request: CaptureTurnRequest) -> CaptureResult:
        """写入一次对话 turn。

        这里做三件事：幂等去重、L0 原始事件落库、通知 pipeline 可能需要抽取 L1。
        """
        await self.initialize()
        digest = request_hash(request)
        cached = self._idempotency.get(request.idempotency_key, digest)
        if cached is not None:
            return cached

        recorded_at = datetime.now(timezone.utc)
        event_ids = []
        for index, message in enumerate(sanitize_messages(request.messages)):
            # event_id 由请求稳定字段推导，配合 upsert 能让重复提交保持可预测结果。
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
        await self.pipeline.notify_conversation(request.session_key, tenant_id=request.tenant_id)
        increment("oom_capture_total")
        return result

    async def search_conversations(self, request: ConversationSearchRequest) -> ConversationSearchResult:
        """搜索 L0 原始对话，用于证据下钻和全文检索。"""
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
        """搜索 L1 原子记忆，优先走 FTS + Vector 的混合召回。"""
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
        """Agent 回复前召回动态上下文。

        召回同时查 L1 和 L0：L1 提供结构化事实，L0 提供更接近原文的证据片段。
        """
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

    async def flush_l1_session(self, session_key: str, tenant_id: str = "default") -> None:
        await self.initialize()
        await self.pipeline.flush_session(session_key, tenant_id=tenant_id)

    @staticmethod
    def _event_id(request: CaptureTurnRequest, index: int) -> str:
        raw = f"{request.tenant_id}:{request.session_key}:{request.idempotency_key}:{index}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))

    @staticmethod
    def _embedding_for(content: str) -> list[float]:
        length = float(len(content))
        checksum = float(sum(ord(char) for char in content) % 997)
        return [length, checksum, 1.0]

    async def _run_l1_for_session(self, session_key: str, tenant_id: str = "default") -> int:
        """最小 L1 pipeline。

        当前实现把 user/assistant 事件直接映射为 episodic memory；后续 LLM 抽取器可在
        这个边界替换进去，而 API 和 store 契约不需要变化。
        """
        events = await self.store.query_l0_for_l1(
            filters={"tenant_id": tenant_id, "session_key": session_key}, limit=100
        )
        count = 0
        for event in events:
            if event.role not in {"user", "assistant"}:
                continue
            memory = MemoryAtom(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"l1:{event.id}")),
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                agent_id=event.agent_id,
                session_id=event.session_id,
                session_key=event.session_key,
                content=event.content,
                type="episodic",
                priority=50,
                confidence=0.7,
                source_event_ids=[event.id],
                timestamps=[event.event_ts.isoformat()],
                metadata={"source": "pipeline_l1"},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            await self.store.upsert_l1(memory, embedding=self._embedding_for(memory.content))
            count += 1
        if count:
            state = self.pipeline.state_for(session_key, tenant_id=tenant_id)
            if state is not None:
                state.last_l1_cursor = events[-1].id
            # L1 有新增后只标记 L2 待处理，由后续调度器决定何时归纳场景。
            self.pipeline.trigger_l2(session_key, tenant_id=tenant_id)
        return count

    async def _search_l1_hybrid(
        self, query: str, limit: int, filters: dict[str, str | None]
    ) -> list:
        """融合关键词与向量检索。

        Store 暴露能力标记，MemoryCore 根据后端能力自动降级到 FTS，避免调用方关心
        SQLite/Postgres 的差异。
        """
        capabilities = self.store.capabilities()
        fts_hits = await self.store.search_l1_fts(query, limit=limit, filters=filters)
        if not capabilities.vector_search:
            return fts_hits

        vector_hits = await self.store.search_l1_vector(self._embedding_for(query), limit=limit, filters=filters)
        hits_by_id = {hit.memory.id: hit for hit in [*fts_hits, *vector_hits]}
        # RRF 只需要各路排序的 ID 列表，最终再回填原始 hit，保留业务对象结构。
        merged = rrf_merge(
            [[hit.memory.id for hit in fts_hits], [hit.memory.id for hit in vector_hits]],
            limit=limit,
        )
        return [hits_by_id[hit.id].model_copy(update={"score": hit.score}) for hit in merged]
