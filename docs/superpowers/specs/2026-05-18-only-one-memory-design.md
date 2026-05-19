# Only-One-Memory 设计

日期：2026-05-18

## 1. 目标

Only-One-Memory 是一个 Python 原生的 Agent Memory Runtime。它应该尽可能还原 TencentDB-Agent-Memory 的核心架构和运行行为，同时提供 REST-first 接口，方便 Python Agent、飞书机器人、MCP Agent、LangGraph、CrewAI 和自研运行时接入。

本项目不是直接包装一个 Node sidecar，而是对记忆运行时进行高保真的 Python 复刻：

- `TdaiCore` 对应为 `MemoryCore`。
- OpenClaw hooks 对应为 FastAPI 端点和 Python SDK。
- `IMemoryStore` 对应为具备运行时能力声明的 Python `MemoryStore` protocol。
- TencentDB-Agent-Memory 的提示词在 MIT 许可下尽可能直接翻译或复用，并保留 attribution。
- 实现分阶段推进，但代码设计覆盖完整系统。

核心原则：

- L0 保存原始证据。
- L1 保存原子化、可检索的记忆。
- L2 将记忆整合为场景块。
- L3 维护稳定的 persona/profile 上下文。
- Recall 负责低延迟注入 stable 和 dynamic context。
- Pipeline 异步演化记忆。
- Store adapters 保持 SQLite 和 Postgres 可切换。
- Context offload 压缩长任务工具日志，同时不丢失可追溯性。
- 项目必须使用 `uv` 管理 Python 版本、虚拟环境、依赖、锁文件和命令执行；不使用裸 `pip`、Poetry 或 PDM 作为项目管理入口。
- 编写代码时，注释默认使用中文；只有外部协议字段、第三方 API 名称、固定错误文本或上游英文术语需要精确保留时，才在注释中使用英文。

## 2. 参照系统

本设计基于本地参照仓库：

`D:\dev\agent\TencentDB-Agent-Memory`

重要源码文件：

- `src/core/tdai-core.ts`：负责 recall、capture、search 和 pipeline 管理的 host-neutral facade。
- `src/core/store/types.ts`：与后端无关的 store 接口和 capability flags。
- `src/core/hooks/auto-capture.ts`：L0 capture 和 deferred embedding 行为。
- `src/core/hooks/auto-recall.ts`：hybrid recall、stable/dynamic context 拆分和 timeout 行为。
- `src/utils/pipeline-manager.ts`：L0 -> L1 -> L2 -> L3 pipeline 调度。
- `src/core/prompts/l1-extraction.ts`：L1 情境切分和记忆抽取提示词。
- `src/core/prompts/l1-dedup.ts`：L1 冲突检测和合并提示词。
- `src/core/prompts/scene-extraction.ts`：L2 场景块提示词和文件操作规则。
- `src/core/prompts/persona-generation.ts`：L3 persona 提示词和 persona 文件约束。
- `src/offload/*`：context offload、refs、Mermaid 和压缩行为。

## 3. 许可与提示词复用

TencentDB-Agent-Memory 使用 MIT License。本项目可以翻译和复用其提示词内容与设计结构，前提是保留 attribution 和 license notices。

必需文件：

- `docs/attribution/tencentdb-agent-memory.md`
- `NOTICE` 或 README attribution section
- `memory_core/prompts/attribution.py`

Attribution 文本应说明：部分提示词设计和记忆架构改编自 TencentDB-Agent-Memory，并遵循 MIT License。

Prompt 模块应保留来源映射注释，例如：

```python
# 改编自 TencentDB-Agent-Memory:
# src/core/prompts/l1-extraction.ts
# License: MIT
```

## 4. 架构

运行时形态：

```text
Agent Runtime / Bot / SDK / MCP / LangGraph
        -> REST / Python SDK
FastAPI Adapter
        -> MemoryCore
        -> Domain Services
           L0 Capture / L1 Extract / L2 Scene / L3 Persona
           Recall / Search / Offload / Admin
        -> Pipeline Manager
        -> Store Adapter
           SQLite / Postgres / future vector stores
        -> Storage + Index
```

`MemoryCore` 是稳定的业务入口。API routes、SDK、CLI、workers 和未来的 MCP adapters 都应该调用 `MemoryCore`，而不是直接使用 store 或 service。

FastAPI 只作为 adapter。它负责校验 HTTP payload、解析依赖、映射 HTTP 错误，但不拥有记忆业务逻辑。

## 5. 建议目录结构

```text
only_one_memory/
  app/
    main.py
    dependencies.py
    api/
      recall.py
      capture.py
      search.py
      sessions.py
      scenes.py
      profiles.py
      offload.py
      admin.py
      health.py

  memory_core/
    core.py
    config.py
    types.py
    errors.py

    capture/
      l0_recorder.py
      idempotency.py
      sanitizer.py

    recall/
      auto_recall.py
      hybrid.py
      rrf.py
      prompt_formatter.py

    extraction/
      l1_extractor.py
      l1_dedup.py
      l1_writer.py
      l1_reader.py

    scene/
      scene_extractor.py
      scene_index.py
      scene_format.py
      scene_navigation.py

    persona/
      persona_trigger.py
      persona_generator.py

    prompts/
      l1_extraction.py
      l1_dedup.py
      scene_extraction.py
      persona_generation.py
      attribution.py

    pipeline/
      manager.py
      jobs.py
      checkpoint.py
      locks.py
      scheduler.py

    stores/
      base.py
      sqlite_store.py
      postgres_store.py
      capabilities.py

    embeddings/
      base.py
      openai_compatible.py
      noop.py

    llm/
      base.py
      openai_compatible.py
      json_utils.py
      tool_runner.py

    offload/
      ref_store.py
      state_manager.py
      mermaid_builder.py
      restore.py
      compressor.py

    observability/
      events.py
      metrics.py
      audit.py

  migrations/
    sqlite/
    postgres/

  tests/
  docs/
    design/
    attribution/
  .python-version
  pyproject.toml
  uv.lock
```

项目管理约束：

- 使用 `uv init --bare --name only-one-memory --vcs none` 初始化项目管理文件，并使用 `uv python pin 3.11` 固定 Python 版本；包目录按本文档的 `only_one_memory/` 结构创建。
- 使用 `uv add ...` 和 `uv add --dev ...` 管理依赖；所有依赖变更必须更新 `pyproject.toml` 与 `uv.lock`。
- 使用 `uv sync` 创建和同步本地环境。
- 使用 `uv run ...` 执行测试、lint、type check、迁移和开发服务，例如 `uv run pytest`、`uv run ruff check .`、`uv run pyright`。
- CI 和本地文档中的命令必须以 `uv` 为统一入口，避免出现裸 `pytest`、`ruff`、`pyright`、`alembic` 命令。
- `.python-version` 固定项目 Python 主版本，V0.1 默认 `3.11`。

代码注释约束：

- 业务代码、测试辅助代码和迁移脚本中的人工注释默认使用中文。
- 注释应解释业务意图、约束、降级原因或上游兼容背景，避免写“给变量赋值”这类重复代码表面的注释。
- TencentDB-Agent-Memory 来源映射注释可以保留英文路径和 License 名称，但说明文字使用中文。

## 6. MemoryCore

`MemoryCore` 对齐 TencentDB-Agent-Memory 的 `TdaiCore`。

公开方法：

```python
class MemoryCore:
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...

    async def before_recall(self, request: BeforeRecallRequest) -> RecallResult: ...
    async def commit_turn(self, turn: CompletedTurn) -> CaptureResult: ...

    async def search_memories(self, params: MemorySearchParams) -> MemorySearchResult: ...
    async def search_conversations(self, params: ConversationSearchParams) -> ConversationSearchResult: ...

    async def end_session(self, session_key: str) -> None: ...
    async def get_pipeline_status(self) -> PipelineStatus: ...
```

内部状态：

- config
- logger
- store
- embedding service
- LLM runner factory
- pipeline manager
- store readiness gate
- scheduler start gate
- background task registry

执行链路：

```text
POST /v1/recall/before
  -> BeforeRecallRequest
  -> MemoryCore.before_recall()
  -> recall.auto_recall()
  -> L3 persona + L2 scene navigation + L1 hybrid search
  -> stable_context + dynamic_context

Agent 调用 LLM

POST /v1/capture/turn
  -> CompletedTurn
  -> MemoryCore.commit_turn()
  -> capture.l0_recorder
  -> store.upsert_l0
  -> pipeline.notify_conversation
  -> quick response

后台 pipeline:
  L1 extract/dedup/write
  -> L2 scene update
  -> L3 persona update
```

重要语义：

- `before_recall()` 位于用户等待路径上，必须有 timeout。
- `commit_turn()` 只记录 L0 并通知 pipeline；它不会同步运行 L1/L2/L3。
- `end_session()` 只 flush 指定 session，不能销毁全局 scheduler 状态。
- `shutdown()` 会 drain 后台任务，在有界 timeout 内 flush pending work，并关闭 stores。

## 7. 领域模型

请求模型和持久化记录中应包含通用身份字段：

- `tenant_id`
- `user_id`
- `agent_id`
- `session_id`
- `session_key`
- `trace_id`
- `metadata`

### L0Event

```python
class L0Event(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    agent_id: str | None
    session_id: str
    session_key: str
    role: Literal["user", "assistant", "tool", "system", "event"]
    content: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_result_ref: str | None = None
    metadata: dict = {}
    event_ts: datetime
    recorded_at: datetime
```

### MemoryAtom

为了与 Tencent prompt 保持高保真，初始 L1 类型为：

- `persona`
- `episodic`
- `instruction`

```python
class MemoryAtom(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    agent_id: str | None
    session_id: str
    session_key: str
    content: str
    type: Literal["persona", "episodic", "instruction"]
    priority: int
    confidence: float = 0.8
    scene_name: str
    source_event_ids: list[str]
    timestamps: list[str] = []
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
```

### SceneBlock

```python
class SceneBlock(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    filename: str
    title: str
    summary: str
    markdown: str
    heat: int
    source_memory_ids: list[str]
    version: int
    created_at: datetime
    updated_at: datetime
```

### PersonaProfile

```python
class PersonaProfile(BaseModel):
    id: str
    tenant_id: str
    scope: Literal["user", "team", "agent", "org"]
    scope_id: str
    markdown: str
    source_scene_ids: list[str]
    version: int
    created_at: datetime
    updated_at: datetime
```

## 8. 数据库 Schema

逻辑表：

```text
tenants
agents
sessions
conversation_events
memories
memory_sources
scene_blocks
scene_sources
persona_profiles
persona_sources
offload_refs
offload_entries
offload_nodes
offload_edges
pipeline_states
pipeline_jobs
idempotency_records
audit_logs
```

必需的可追溯关系：

- `memory_sources`：L1 -> L0 evidence
- `scene_sources`：L2 -> L1 evidence
- `persona_sources`：L3 -> L2 evidence
- offload refs 可被 L0 tool events 和 offload graph nodes 引用

索引：

```text
L0:
  session_key + recorded_at
  tenant_id + user_id + event_ts
  FTS index(content/searchable_content)
  vector index when embedding is enabled

L1:
  tenant_id + user_id + type
  tenant_id + user_id + scene_name
  updated_at
  FTS index(content/searchable_content)
  vector index

L2/L3:
  tenant/scope/version
  summary FTS optional

Pipeline:
  session_key unique
  job status + run_after
```

SQLite：

- FTS5 用于关键词检索。
- V0.1 起支持 sqlite-vec 作为 SQLite 向量检索后端。
- embedding 可同时保留 BLOB/JSON 备份字段，便于重建 sqlite-vec 索引和调试。
- Python brute-force cosine 只作为 sqlite-vec 不可用时的兼容兜底，不作为一期主路径。
- 使用 WAL mode。
- 优先使用 in-process worker。

Postgres：

- V0.1 起支持 PostgresStore，不延后到生产阶段。
- JSONB metadata。
- tsvector + GIN。
- pgvector。
- V0.1 覆盖基础 schema migration、L0 写入、FTS 和 pgvector 检索；V0.2 在同一后端能力上补齐 L1 memories。
- DB-backed workers 后续使用 `SELECT ... FOR UPDATE SKIP LOCKED`。
- 分布式安全后续使用 advisory locks 或 job-table locks。

## 9. REST API 与 SDK

主流程：

```text
POST /v1/recall/before
POST /v1/capture/turn
POST /v1/sessions/{session_key}/end
```

搜索和工具流程：

```text
POST /v1/memories/search
POST /v1/conversations/search
POST /v1/offload/restore
```

管理流程：

```text
GET    /v1/scenes
GET    /v1/scenes/{scene_id}
PATCH  /v1/scenes/{scene_id}

GET    /v1/profiles/{scope}/{scope_id}
PATCH  /v1/profiles/{scope}/{scope_id}

GET    /v1/admin/pipeline/status
POST   /v1/admin/pipeline/run
POST   /v1/admin/reindex
POST   /v1/admin/export
POST   /v1/admin/import
DELETE /v1/admin/users/{user_id}

GET    /v1/health
GET    /v1/metrics
```

Python SDK 形态：

```python
client = MemoryClient(base_url="http://localhost:8710", api_key="...")

recall = await client.before_recall(
    tenant_id="default",
    user_id=user_id,
    agent_id=agent_id,
    session_id=session_id,
    session_key=session_key,
    user_text=user_text,
)

messages = [
    {"role": "system", "content": base_prompt + "\n\n" + recall.stable_context},
    *history,
    {"role": "user", "content": recall.dynamic_context + "\n\n" + user_text},
]

await client.commit_turn(
    tenant_id="default",
    user_id=user_id,
    agent_id=agent_id,
    session_id=session_id,
    session_key=session_key,
    idempotency_key=turn_id,
    messages=[...],
    tool_events=[...],
)
```

安全：

- V0 使用 API key auth。
- V1 增加 tenant-scoped API keys。
- V2 可增加 JWT/OIDC。
- `trace_id` 全链路透传。
- `/v1/capture/turn` 必须提供 `idempotency_key`。
- Recall/search 失败时降级为空结果；capture 持久化失败时返回错误。

## 10. Store Adapter

`MemoryStore` 对齐 Tencent 的 `IMemoryStore`。

```python
@dataclass(frozen=True)
class StoreCapabilities:
    vector_search: bool
    fts_search: bool
    native_hybrid_search: bool
    sparse_vectors: bool
    deferred_embedding: bool
    json_query: bool
    transactional: bool
    distributed_lock: bool
```

```python
class MemoryStore(Protocol):
    async def init(self, provider_info: EmbeddingProviderInfo | None = None) -> StoreInitResult: ...
    async def close(self) -> None: ...
    def capabilities(self) -> StoreCapabilities: ...
    def is_degraded(self) -> bool: ...

    async def upsert_l0(self, record: L0Event, embedding: list[float] | None = None) -> bool: ...
    async def update_l0_embedding(self, event_id: str, embedding: list[float]) -> bool: ...
    async def query_l0_for_l1(self, session_key: str, after_cursor: str | None, limit: int) -> list[L0Event]: ...
    async def search_l0_fts(self, query: str, limit: int, filters: SearchFilters) -> list[L0SearchHit]: ...
    async def search_l0_vector(self, embedding: list[float], limit: int, filters: SearchFilters) -> list[L0SearchHit]: ...

    async def upsert_l1(self, memory: MemoryAtom, embedding: list[float] | None = None) -> bool: ...
    async def delete_l1(self, memory_id: str) -> bool: ...
    async def query_l1_records(self, filters: L1QueryFilters) -> list[MemoryAtom]: ...
    async def search_l1_fts(self, query: str, limit: int, filters: SearchFilters) -> list[MemorySearchHit]: ...
    async def search_l1_vector(self, embedding: list[float], limit: int, filters: SearchFilters) -> list[MemorySearchHit]: ...
    async def search_l1_hybrid(self, params: HybridSearchParams) -> list[MemorySearchHit]: ...

    async def upsert_scene(self, scene: SceneBlock) -> bool: ...
    async def list_scenes(self, filters: SceneFilters) -> list[SceneBlock]: ...
    async def upsert_profile(self, profile: PersonaProfile) -> bool: ...
    async def get_profile(self, scope: str, scope_id: str) -> PersonaProfile | None: ...

    async def reindex_all(self, embed_fn: Callable[[str], Awaitable[list[float]]]) -> ReindexResult: ...
```

规则：

- Recall 使用的 store 方法应 fail closed：返回空结果或 `False`，并记录日志。
- Admin 和 migration 方法可以抛出显式错误。
- Capabilities 表示运行时真实能力，而不是配置意图。
- Embedding provider/model/dimension 变化时应产生 `needs_reindex=True`。

## 11. Recall 与 Search

Recall 对齐 Tencent 的 auto-recall：

```text
1. Clean user_text.
2. Prepare L3 persona, L2 scene navigation, and L1 hybrid search.
3. Use native hybrid if the store supports it.
4. Otherwise run FTS and vector search, then RRF merge.
5. Apply secondary boosts.
6. Truncate by token budget.
7. Return stable_context and dynamic_context.
```

Context 拆分：

```text
stable_context:
  <user-persona>...</user-persona>
  <scene-navigation>...</scene-navigation>
  <memory-tools-guide>...</memory-tools-guide>

dynamic_context:
  <recalled-memories>
  - [persona|scene] ...
  - [episodic|scene] ...
  </recalled-memories>
```

RRF：

```python
def rrf_merge(lists: list[list[SearchHit]], k: int = 60) -> list[SearchHit]:
    scores = {}
    best = {}
    for hits in lists:
        for rank, hit in enumerate(hits, start=1):
            scores[hit.id] = scores.get(hit.id, 0.0) + 1.0 / (k + rank)
            best.setdefault(hit.id, hit)
    return sorted(
        (best[id].with_score(score) for id, score in scores.items()),
        key=lambda x: x.score,
        reverse=True,
    )
```

加权项：

```text
final_score =
  rrf_score
  + priority_boost
  + confidence_boost
  + recency_boost
  + type_boost
```

默认配置：

```yaml
recall:
  enabled: true
  strategy: hybrid
  max_results: 5
  timeout_ms: 800
  score_threshold: 0.25
  token_budget: 1200

embedding:
  recall_timeout_ms: 1000
```

搜索工具：

- `/v1/memories/search` 搜索 L1 结构化记忆。
- `/v1/conversations/search` 搜索 L0 原始证据。

两者都应该返回 Agent 可读文本和结构化 JSON 字段。

## 12. Capture 与 Pipeline

Capture 流程：

```text
1. Validate tenant/user/session/session_key.
2. Check idempotency_key.
3. Sanitize messages and tool events.
4. Atomically write L0 conversation_events.
5. Write FTS/searchable_content.
6. If store supports deferred_embedding:
     write metadata + FTS before returning
     run embed_batch + update_l0_embedding in background
   else:
     embed synchronously and upsert_l0 with embedding
7. pipeline.notify_conversation(session_key)
8. Return capture result and emit metrics.
```

幂等：

```text
idempotency_records:
  tenant_id
  idempotency_key
  request_hash
  response_json
  created_at
  expires_at
```

相同 key 且相同 hash 返回缓存响应。相同 key 但不同 hash 返回冲突。

Pipeline 触发：

```text
L1:
  threshold: conversation_count >= effective_threshold
  idle timeout: user stops for l1_idle_timeout_seconds
  flush: session end or shutdown

Warmup:
  new session threshold = 1
  after each successful L1: 1 -> 2 -> 4 -> every_n_conversations

L2:
  after L1 success:
    desired = max(now + l2_delay_after_l1, last_l2 + l2_min_interval)
    timer can only move earlier, not later
  after L2 completion:
    arm max_interval timer
  cold sessions:
    max_interval timer stops when outside active window

L3:
  triggered after L2
  global serial queue
  pending flag reruns L3 after current run if new L2 work arrived
```

Pipeline state：

```text
session_key
conversation_count
warmup_threshold
last_l1_cursor
last_scene_name
l2_cursor
l2_pending_l1_count
last_l2_at
last_activity_at
l1_retry_count
```

V0 使用 in-process asyncio queues。V1 增加 DB-backed `pipeline_jobs` 和独立 worker process。

## 13. Prompt System

Prompt 模块是一等代码，必须带来源 attribution、parser tests 和 schema validation。

### L1 Extraction

改编自 `src/core/prompts/l1-extraction.ts`。

输入：

- `previous_scene_name`
- `background_messages`：只作为上下文，不从中抽取
- `new_messages`：只从这里抽取

输出：

```text
[
  {
    "scene_name": "...",
    "message_ids": ["..."],
    "memories": [
      {
        "content": "...",
        "type": "persona|episodic|instruction",
        "priority": 80,
        "source_message_ids": ["..."],
        "metadata": {}
      }
    ]
  }
]
```

Parser 必须处理 markdown fence、额外解释文本、控制字符、缺失 metadata、空 memories 和非法 type。

### L1 Dedup

改编自 `src/core/prompts/l1-dedup.ts`。

动作：

- `store`
- `update`
- `skip`
- `merge`

Dedup 候选召回：

- 有 vector 时使用 vector top-K
- 否则使用 FTS top-K fallback
- 两者都不可用时跳过 dedup，全部 store

### L2 Scene

改编自 `src/core/prompts/scene-extraction.ts`。

提示词语义应尽量贴近 Tencent 版本：scene files 是 Markdown narrative documents，不是扁平列表；LLM 可以 read/write/edit scene files；删除用 `[DELETED]` 表示。

Python 不应让 LLM 直接接触真实文件系统，而应使用受控 tool runner：

```text
SceneToolRunner:
  read_scene(filename)
  write_scene(filename, content)
  edit_scene(filename, edits)
  delete_scene(filename)
```

强制约束：

- 禁止路径穿越
- read whitelist 来自 existing scene file list
- 只能操作 `.md` scene files
- delete 映射为 `[DELETED]`
- 工程侧同步 scene index

Scene Markdown 格式：

```markdown
-----META-START-----
created: ...
updated: ...
summary: ...
heat: ...
-----META-END-----

## 用户基础信息
## 用户核心特征
## 用户偏好
## 隐性信号
## 核心叙事
## 演变轨迹
## 待确认/矛盾点
```

### L3 Persona

改编自 `src/core/prompts/persona-generation.ts`。

输入：

- `mode`：`first` 或 `incremental`
- `current_time`
- `total_processed`
- `scene_count`
- `changed_scene_count`
- `changed_scenes_content`
- `existing_persona`
- `trigger_info`

Python 使用受控 persona runner：

```text
PersonaToolRunner:
  write_persona(content)
  edit_persona(edits)
```

约束：

- 只能操作 `persona.md`
- 不允许读取 scene files
- 模型输出中不允许包含 scene navigation
- persona 正文目标长度不超过 2000 字符
- 工程侧在生成后追加 scene navigation

## 14. Context Offload

Offload 对齐 Tencent 的短期符号化记忆。

表：

```text
offload_refs
offload_entries
offload_nodes
offload_edges
```

REST API：

```text
POST /v1/offload/refs
GET  /v1/offload/refs/{ref_id}

POST /v1/offload/entries
GET  /v1/offload/entries?session_id=...

POST /v1/offload/graph/update
GET  /v1/offload/graph/{session_id}

POST /v1/offload/restore
```

分层：

```text
L1 offload:
  tool pair -> summary + score + result_ref

L1.5 task judgment:
  classify new task, continued task, completed task

L2 Mermaid:
  offload entries -> Mermaid graph
  node_id maps back to result_ref

L3 compression:
  mild: replace old tool results with summaries
  aggressive: delete older messages and inject Mermaid
  emergency: keep recent user messages and task graph
```

实现阶段：

- V0.5a：refs + restore API
- V0.5b：tool pair summary + offload entries
- V0.5c：Mermaid graph generation
- V0.5d：compressor policy + SDK helper

## 15. 配置

初始配置形态：

```yaml
server:
  host: 0.0.0.0
  port: 8710
  auth:
    mode: api_key

store:
  backend: sqlite
  sqlite:
    path: ./data/memory.db
    vector_backend: sqlite_vec  # sqlite_vec | blob_bruteforce
  postgres:
    dsn: postgresql+asyncpg://user:pass@localhost:5432/memory
    vector_dim: 1536
    vector_index: hnsw
    text_search_config: simple

embedding:
  enabled: true
  provider: openai_compatible
  base_url: https://api.example.com/v1
  api_key: ${EMBEDDING_API_KEY}
  model: text-embedding-model
  dimensions: 1536
  timeout_ms: 10000
  recall_timeout_ms: 1000
  capture_timeout_ms: 15000

llm:
  provider: openai_compatible
  base_url: https://api.example.com/v1
  api_key: ${LLM_API_KEY}
  model: gpt-4.1
  timeout_ms: 120000
  json_mode: true

recall:
  enabled: true
  strategy: hybrid
  max_results: 5
  timeout_ms: 800
  score_threshold: 0.25
  token_budget: 1200

pipeline:
  enabled: true
  every_n_conversations: 5
  enable_warmup: true
  l1_idle_timeout_seconds: 600
  l2_delay_after_l1_seconds: 90
  l2_min_interval_seconds: 900
  l2_max_interval_seconds: 3600
  session_active_window_hours: 24
  persona_trigger_every_n: 50

offload:
  enabled: true
  default_context_window: 200000
  max_ref_chars_inline: 2000
  force_trigger_threshold: 4
  mild_offload_ratio: 0.5
  aggressive_compress_ratio: 0.85
  mmd_max_token_ratio: 0.2
```

## 16. 测试策略

单元测试：

- config validation
- Pydantic schemas
- store init/upsert/query/search for SQLite/sqlite-vec and Postgres/pgvector
- RRF and scoring
- recall timeout fallback
- capture idempotency
- deferred embedding registry

Prompt/parser 测试：

- L1 extraction JSON parsing
- L1 dedup decisions
- hallucinated record IDs
- scene tool sandbox
- persona tool sandbox

Pipeline 测试：

- threshold trigger
- warmup progression
- idle timeout
- L1 retry
- L2 delay/min/max interval
- L3 pending rerun
- session-end scoped flush
- shutdown background drain

API 测试：

- `/health`
- cold-start `/v1/recall/before`
- `/v1/capture/turn`
- `/v1/memories/search`
- `/v1/conversations/search`
- `/v1/admin/pipeline/status`
- user deletion

集成测试：

- backend matrix: SQLite + sqlite-vec, Postgres + pgvector
- capture turns -> run L1 -> search -> run L2 -> run L3 -> recall
- embedding disabled -> FTS fallback
- FTS unavailable -> vector fallback
- restart -> checkpoint restore

质量门禁：

- `uv lock --check`
- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest`
- `uv run alembic` 或迁移冒烟测试命令
- OpenAPI generation check

## 17. 实现计划

### V0.1 REST + MemoryCore + SQLite/Postgres L0

- FastAPI skeleton
- uv project skeleton：`.python-version`、`pyproject.toml`、`uv.lock`
- `MemoryCore` lifecycle
- config
- SQLite basic schema + FTS5 + sqlite-vec
- Postgres basic schema + JSONB + tsvector/GIN + pgvector
- store backend selection and migration smoke tests for both backends
- `/v1/capture/turn`
- `/v1/conversations/search` via FTS/vector according to backend capabilities
- `/v1/health`
- idempotency
- tests

### V0.2 L1 + Hybrid Recall

- prompt migration：L1 extraction and dedup
- L1 extractor
- MemoryAtom store for both SQLite/sqlite-vec and Postgres/pgvector
- embedding provider
- RRF
- `/v1/recall/before`
- `/v1/memories/search`
- pipeline L1 threshold and idle
- tests

### V0.3 Pipeline 完整化 + Worker 化

- warmup, L2, L3 queues
- checkpoint restore
- Postgres worker locking with `SELECT ... FOR UPDATE SKIP LOCKED`
- advisory locks or job-table locks
- admin reindex
- optional separate worker

### V0.4 L2/L3

- scene prompt + SceneToolRunner
- scene blocks + scene index
- persona prompt + PersonaToolRunner
- scene navigation
- profiles API
- attribution docs

### V0.5 Context Offload

- refs
- restore
- offload entries
- Mermaid builder
- compressor SDK helper

### V0.6 生产强化

- auth scopes
- audit/export/import/delete-user
- metrics
- migration tooling
- Docker

## 18. 成功标准

V0.1 成功标准：Python Agent 可以通过 REST 记录 turns，并在 SQLite 和 Postgres 两种后端下完成重启后的原始对话搜索；SQLite 路径支持 FTS5 + sqlite-vec，Postgres 路径支持 tsvector/GIN + pgvector。

V0.2 成功标准：已捕获的 turns 可以生成 L1 memories，并且下一次 recall 调用能返回 stable 和 dynamic context。

V0.4 成功标准：L1 memories 可以演化为 scene blocks 和 persona profile，并能追溯回 L0 evidence。

V0.5 成功标准：长工具输出可以 offload 到 refs，总结为 graph nodes，通过 `node_id` 或 `result_ref` 恢复，并能被 Agent 使用且不丢失原始证据。

## 19. 自检

完整性扫描：没有遗留标记，章节完整。

一致性检查：架构始终通过 `MemoryCore` 路由行为，保持 FastAPI 作为 adapter，并保留 L0/L1/L2/L3 可追溯性。

范围检查：这是完整系统设计，但实现已明确分阶段推进。V0.1 和 V0.2 足够小，可以分别制定实现计划。

歧义检查：prompt 复用明确要求 MIT attribution 和高保真；L1 类型有意限制为 Tencent 初始的 `persona`、`episodic` 和 `instruction`，以保持兼容性。
