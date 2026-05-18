可以做，而且这个方向比“直接嵌 Node sidecar”更适合你的 Python Agent。我的建议是：**不要逐行翻译 TencentDB-Agent-Memory，而是做一个 Python 版、REST-first、Store-agnostic 的 Memory Server**。它的核心能力一比一对齐 Tencent 的架构：L0 原始对话、L1 原子记忆、L2 场景块、L3 Persona、Hybrid Recall、异步 Pipeline、Context Offload。REST API 是外壳，真正核心应该是 `MemoryCore`。

Tencent 这个 repo 本身也不是简单 OpenClaw 插件：它的 `TdaiCore` 被源码描述为 host-neutral facade，也就是 OpenClaw 和 Hermes/Gateway 都调用同一个核心入口，负责 recall、capture、search 和 pipeline 管理。这个设计非常适合你在 Python 里复刻成 `MemoryCore + FastAPI Adapter`。([GitHub][1])

---

# 1. 总体设计目标

你要做的不是一个“记忆数据库”，而是一个 **Agent Memory Runtime**。

它应该暴露给任何 Agent Runtime 使用：

```text
Python Agent / Feishu Bot / MCP Agent / LangGraph / CrewAI / 自研 Runtime
        ↓ REST / SDK
Python Memory Server
        ↓
MemoryCore
        ↓
Store Adapter: SQLite / PostgreSQL
        ↓
L0 / L1 / L2 / L3 / Offload / Recall / Pipeline
```

核心目标：

```text
1. REST-first：任何语言的 Agent 都能调用
2. Python-native：FastAPI + Pydantic + SQLAlchemy/Alembic
3. Store-agnostic：初期 SQLite / Postgres，后续可扩 Milvus、Qdrant、TCVDB、Elastic
4. Evidence-first：所有 L1/L2/L3 都能追溯到 L0 原始证据
5. Async Pipeline：L1/L2/L3 不阻塞主对话
6. Hybrid Recall：关键词 + 向量 + RRF + priority/recency/confidence
7. Offload-ready：支持工具日志 refs、Mermaid 工作图、node_id/result_ref 下钻
```

Tencent 的 README 明确把它的核心概括成“符号化短期记忆 + 分层式长期记忆”，长期记忆是 L0 Conversation → L1 Atom → L2 Scenario → L3 Persona，短期记忆是 refs 原文、jsonl 摘要和 Mermaid 任务画布的分层。你的 Python 版应该保持这个语义结构。([GitHub][2])

---

# 2. 推荐系统架构

我建议拆成 6 层。

```text
┌──────────────────────────────────────────────┐
│                REST API Layer                 │
│ FastAPI / Auth / Tenant / Rate Limit / Trace  │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│              MemoryCore Layer                 │
│ before_recall / commit_turn / search / admin  │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│              Domain Service Layer             │
│ L0 Capture / L1 Extract / L2 Scene / L3 Persona│
│ Recall / Offload / Dedup / Conflict / Privacy │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│              Pipeline Worker Layer            │
│ Scheduler / Queue / Retry / Checkpoint / Lock │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│              Store Adapter Layer              │
│ SQLiteStore / PostgresStore / FutureStore     │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│              Storage + Index Layer            │
│ SQLite FTS5/sqlite-vec or Postgres FTS/pgvector│
└──────────────────────────────────────────────┘
```

---

# 3. Python 项目结构

建议项目先按这个结构建：

```text
agent_memory_server/
  app/
    main.py                       # FastAPI app
    api/
      recall.py
      capture.py
      search.py
      profiles.py
      scenes.py
      offload.py
      admin.py
      health.py

  memory_core/
    core.py                       # MemoryCore，等价于 TdaiCore
    config.py
    types.py
    errors.py

    capture/
      l0_recorder.py
      checkpoint.py
      idempotency.py

    recall/
      auto_recall.py
      hybrid.py
      rrf.py
      prompt_formatter.py

    extraction/
      l1_extractor.py
      l1_writer.py
      l1_dedup.py
      prompts.py

    scene/
      scene_extractor.py
      scene_index.py
      scene_navigation.py

    persona/
      persona_generator.py
      profile_store.py

    offload/
      ref_store.py
      mermaid_builder.py
      context_compressor.py
      restore.py

    pipeline/
      manager.py
      jobs.py
      locks.py
      scheduler.py

    stores/
      base.py                     # MemoryStore Protocol
      sqlite_store.py
      postgres_store.py
      capabilities.py

    embeddings/
      base.py
      openai_compatible.py
      local.py
      noop.py

    llm/
      base.py
      openai_compatible.py
      json_mode.py

    observability/
      metrics.py
      events.py
      audit.py

  migrations/
    sqlite/
    postgres/

  tests/
  pyproject.toml
```

最重要的是 `core.py`，它应该像 Tencent 的 `TdaiCore` 一样，不依赖 FastAPI、不依赖具体 Agent Runtime，只暴露核心方法：

```python
class MemoryCore:
    async def initialize(self) -> None: ...

    async def before_recall(
        self,
        user_text: str,
        session_key: str,
        user_id: str,
        agent_id: str | None = None,
    ) -> RecallResult: ...

    async def commit_turn(
        self,
        turn: CompletedTurn,
    ) -> CaptureResult: ...

    async def search_memories(
        self,
        params: MemorySearchParams,
    ) -> MemorySearchResult: ...

    async def search_conversations(
        self,
        params: ConversationSearchParams,
    ) -> ConversationSearchResult: ...

    async def end_session(self, session_key: str) -> None: ...

    async def shutdown(self) -> None: ...
```

REST API 只负责把 HTTP 请求转成这些方法调用。

---

# 4. 核心数据分层

## L0：原始证据层

L0 是所有记忆的底座。不要先总结，先完整留痕。

```text
L0 保存：
- user message
- assistant message
- tool call
- tool result
- system/runtime event
- 原始时间戳
- session_id
- source channel
- result_ref
- metadata
```

Tencent 的 auto-capture 设计也是先记录 L0，然后通知 PipelineManager；源码注释明确说 extraction 不在 capture 里触发，而是由 pipeline manager 决定何时跑。这个原则你应该完全保留。([GitHub][3])

## L1：结构化原子记忆

L1 不是摘要，而是可检索、可去重、可追溯的 memory atom。

```python
class MemoryAtom(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    agent_id: str | None
    session_id: str
    session_key: str

    content: str
    type: Literal[
        "persona",
        "episodic",
        "instruction",
        "preference",
        "project",
        "task",
        "constraint",
    ]
    priority: int = 3
    confidence: float = 0.8
    scene_name: str | None = None

    source_event_ids: list[str]
    metadata: dict = {}

    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
```

Tencent 的 L1 extractor 源码描述了类似流程：从 L0 读取最近消息，用 LLM 做 scene-segmented memories，再做批量冲突检测，最后写入 L1。([GitHub][4])

## L2：场景块

L2 是长期主题、项目、场景。

```text
例如：
- 用户正在开发的 Agent 记忆系统
- 用户公司的销售 SOP
- 某个长期项目背景
- 某个健康/训练/饮食长期计划
```

L2 建议既存数据库，也可选 mirror 成 Markdown 文件，方便调试。

```python
class SceneBlock(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    name: str
    markdown: str
    summary: str
    source_memory_ids: list[str]
    version: int
    updated_at: datetime
```

## L3：Persona/Profile

L3 是稳定画像，不要塞太多动态任务状态。

```text
L3 保存：
- 用户长期偏好
- 交流风格
- 工作方式
- 长期项目背景
- 明确要求 agent 长期遵守的规则
```

```python
class PersonaProfile(BaseModel):
    id: str
    tenant_id: str
    scope: Literal["user", "team", "agent", "org"]
    scope_id: str
    markdown: str
    source_scene_ids: list[str]
    version: int
    updated_at: datetime
```

---

# 5. Store 抽象层设计

Tencent 源码里的 `IMemoryStore` 很值得照抄思想：上层只依赖接口，不依赖 SQLite 或 TCVDB；并且通过 capability flags 判断是否支持 vector search、FTS、native hybrid、deferred embedding 等能力。([GitHub][5])

Python 版可以这样设计：

```python
@dataclass
class StoreCapabilities:
    vector_search: bool
    fts_search: bool
    native_hybrid_search: bool
    sparse_vector: bool
    deferred_embedding: bool
    json_query: bool
    transactional: bool
    distributed_lock: bool


class MemoryStore(Protocol):
    async def init(self) -> None: ...
    async def close(self) -> None: ...
    def capabilities(self) -> StoreCapabilities: ...

    # L0
    async def upsert_l0(self, record: L0Event, embedding: list[float] | None = None) -> bool: ...
    async def update_l0_embedding(self, record_id: str, embedding: list[float]) -> bool: ...
    async def search_l0_fts(self, query: str, limit: int) -> list[L0SearchHit]: ...
    async def search_l0_vector(self, embedding: list[float], limit: int) -> list[L0SearchHit]: ...
    async def query_l0_for_l1(self, session_key: str, after_cursor: str | None, limit: int) -> list[L0Event]: ...

    # L1
    async def upsert_l1(self, record: MemoryAtom, embedding: list[float] | None = None) -> bool: ...
    async def delete_l1(self, memory_id: str) -> bool: ...
    async def search_l1_fts(self, query: str, limit: int, filters: dict) -> list[MemoryHit]: ...
    async def search_l1_vector(self, embedding: list[float], limit: int, filters: dict) -> list[MemoryHit]: ...
    async def query_l1_records(self, filters: dict) -> list[MemoryAtom]: ...

    # L2/L3
    async def upsert_scene(self, scene: SceneBlock) -> bool: ...
    async def get_scene_navigation(self, user_id: str) -> str: ...
    async def upsert_profile(self, profile: PersonaProfile) -> bool: ...
    async def get_profile(self, scope: str, scope_id: str) -> PersonaProfile | None: ...

    # Admin
    async def reindex_all(self) -> ReindexResult: ...
```

这会让 SQLite 和 Postgres 都能接入：

```text
SQLiteStore:
  FTS5 + sqlite-vec/SQLite-Vector/embedding BLOB fallback

PostgresStore:
  tsvector + GIN + pgvector + JSONB
```

SQLite FTS5 是官方 SQLite 虚拟表模块，支持用 MATCH 查询全文内容，并可按 rank/BM25 排序；这适合作为本地 keyword retrieval 的底座。([SQLite 主页][6])

Postgres 侧，全文检索可以用 `tsvector` / `tsquery` / `@@`，并用 GIN index 加速；Postgres 文档也建议实际应用通常需要索引，否则全文搜索会太慢。([PostgreSQL][7])

向量侧，Postgres 推荐用 pgvector。pgvector 支持 exact 和 approximate nearest neighbor search，支持 L2、inner product、cosine 等距离，并支持 HNSW 和 IVFFlat 索引。([GitHub][8])

---

# 6. 数据库 Schema 设计

## 6.1 通用逻辑表

无论 SQLite 还是 Postgres，都保持同一组逻辑表。

```text
tenants
agents
sessions
conversation_events       # L0
memories                  # L1
memory_sources            # L1 -> L0 溯源关系
scene_blocks              # L2
persona_profiles          # L3
offload_refs              # 工具结果原文
offload_nodes             # Mermaid / task graph nodes
offload_edges             # Mermaid / task graph edges
pipeline_states
pipeline_jobs
checkpoints
audit_logs
```

---

## 6.2 L0 表

```sql
CREATE TABLE conversation_events (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  agent_id TEXT,
  session_id TEXT NOT NULL,
  session_key TEXT NOT NULL,

  role TEXT NOT NULL,
  content TEXT,
  tool_name TEXT,
  tool_call_id TEXT,
  tool_result_ref TEXT,

  metadata_json TEXT,
  event_ts TIMESTAMP NOT NULL,
  recorded_at TIMESTAMP NOT NULL
);
```

Postgres 可以把 `metadata_json` 改成 `JSONB`。Postgres 官方文档也建议大多数应用优先用 `jsonb`，因为它以分解后的二进制格式存储，处理更快，并支持索引。([PostgreSQL][9])

---

## 6.3 L1 表

```sql
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  agent_id TEXT,
  session_id TEXT,
  session_key TEXT,

  content TEXT NOT NULL,
  type TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 3,
  confidence REAL NOT NULL DEFAULT 0.8,
  scene_name TEXT,

  metadata_json TEXT,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP
);

CREATE TABLE memory_sources (
  memory_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  PRIMARY KEY (memory_id, event_id)
);
```

Postgres 版建议加：

```sql
ALTER TABLE memories
ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;

ALTER TABLE memories
ADD COLUMN embedding vector(1536);

ALTER TABLE memories
ADD COLUMN search_tsv tsvector
GENERATED ALWAYS AS (
  to_tsvector('simple', coalesce(content, ''))
) STORED;

CREATE INDEX memories_search_tsv_idx
ON memories USING GIN (search_tsv);

CREATE INDEX memories_embedding_hnsw_idx
ON memories USING hnsw (embedding vector_cosine_ops);
```

`vector(1536)` 的维度要跟你的 embedding 模型一致。pgvector 文档示例里使用 `CREATE EXTENSION vector` 开启扩展，用 `vector(n)` 存向量，并通过 `<=>` 做 cosine distance，HNSW 的 `ef_search` 越高 recall 越好但速度越慢。([GitHub][8])

SQLite 版建议：

```sql
CREATE VIRTUAL TABLE memories_fts
USING fts5(
  content,
  type,
  scene_name,
  content='memories',
  content_rowid='rowid'
);
```

SQLite vector 初期建议两档：

```text
A 档：安装 sqlite-vec，支持本地向量检索
B 档：无 sqlite-vec 时，把 embedding 存 BLOB，Top-K 用 Python brute force，适合小规模 MVP
```

这能保证产品先跑起来。不要一开始就被 SQLite 向量扩展的部署兼容性卡死。

---

## 6.4 L2 / L3 表

```sql
CREATE TABLE scene_blocks (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  summary TEXT,
  markdown TEXT NOT NULL,
  source_memory_ids_json TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE persona_profiles (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  scope TEXT NOT NULL,
  scope_id TEXT NOT NULL,
  markdown TEXT NOT NULL,
  source_scene_ids_json TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,

  UNIQUE (tenant_id, scope, scope_id)
);
```

---

## 6.5 Offload 表

```sql
CREATE TABLE offload_refs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  content TEXT,
  content_hash TEXT NOT NULL,
  metadata_json TEXT,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE offload_nodes (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  result_ref TEXT,
  status TEXT,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE offload_edges (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  from_node_id TEXT NOT NULL,
  to_node_id TEXT NOT NULL,
  label TEXT
);
```

Tencent 的短期记忆压缩核心就是把完整工具日志放到 refs，向上下文注入 Mermaid 图和 node_id/result_ref，必要时再沿 node_id 下钻恢复原文。你的 Python 版也应该保留这个 `ref → node → graph → restore` 的结构。([GitHub][2])

---

# 7. REST API 设计

## 7.1 Agent 主流程 API

### `POST /v1/recall/before`

Agent 调 LLM 之前调用。

请求：

```json
{
  "tenant_id": "tenant_001",
  "user_id": "user_001",
  "agent_id": "sales_agent",
  "session_id": "session_001",
  "session_key": "feishu:user_001:session_001",
  "user_text": "上次我们说的记忆系统怎么继续做？",
  "max_results": 5
}
```

响应：

```json
{
  "stable_context": "## Persona\n...\n\n## Scene Navigation\n...",
  "dynamic_context": "## Relevant Memories\n1. ...\n2. ...",
  "memories": [
    {
      "id": "mem_001",
      "content": "用户正在开发一个 Python Agent，记忆系统自研。",
      "type": "project",
      "score": 0.87,
      "source_event_ids": ["evt_001", "evt_002"]
    }
  ],
  "scenes": [],
  "profile_version": 12,
  "strategy": "hybrid",
  "latency_ms": 82
}
```

这里要和 Tencent 一样拆成两类上下文：

```text
stable_context:
  L3 persona
  L2 scene navigation
  memory tool guide

dynamic_context:
  本轮 query 相关的 L1 memories
```

这样能避免所有内容都混在一段 prompt 里，也方便后续做 prompt cache。

---

### `POST /v1/capture/turn`

Agent 一轮结束后调用。

请求：

```json
{
  "tenant_id": "tenant_001",
  "user_id": "user_001",
  "agent_id": "sales_agent",
  "session_id": "session_001",
  "session_key": "feishu:user_001:session_001",
  "idempotency_key": "turn_20260518_0001",
  "messages": [
    {
      "role": "user",
      "content": "如果我基于 tencentagentmemory 复刻 Python 版怎么办？",
      "timestamp": "2026-05-18T10:00:00+08:00"
    },
    {
      "role": "assistant",
      "content": "可以做，建议做成 REST API...",
      "timestamp": "2026-05-18T10:00:10+08:00"
    }
  ],
  "tool_events": []
}
```

响应：

```json
{
  "accepted": true,
  "l0_recorded_count": 2,
  "l0_indexed_count": 2,
  "scheduler_notified": true,
  "next_pipeline_hint": {
    "l1_due": false,
    "conversation_count": 3,
    "threshold": 5
  }
}
```

这个接口必须支持幂等。`idempotency_key` 很重要，否则飞书重试、Agent 重放、网络抖动都会导致 L0 重复记录。

---

## 7.2 显式工具 API

### `POST /v1/memories/search`

给 Agent 当工具用，对应 Tencent 的 `tdai_memory_search`。

```json
{
  "tenant_id": "tenant_001",
  "user_id": "user_001",
  "query": "用户的 agent memory 架构偏好",
  "type": "project",
  "scene_name": "agent-memory-system",
  "limit": 10,
  "strategy": "hybrid"
}
```

### `POST /v1/conversations/search`

给 Agent 查 L0 原始证据，对应 Tencent 的 `tdai_conversation_search`。

```json
{
  "tenant_id": "tenant_001",
  "user_id": "user_001",
  "query": "tencentagentmemory python restapi",
  "session_id": "session_001",
  "from": "2026-05-01T00:00:00+08:00",
  "to": "2026-05-18T23:59:59+08:00",
  "limit": 10
}
```

---

## 7.3 L2 / L3 API

```text
GET    /v1/scenes
GET    /v1/scenes/{scene_id}
PATCH  /v1/scenes/{scene_id}
GET    /v1/profiles/{scope}/{scope_id}
PATCH  /v1/profiles/{scope}/{scope_id}
```

允许人工编辑 L2/L3 很重要。Tencent 也强调 L2 Scenario、L3 Persona、Mermaid、refs 都是白盒可调试的，而不是黑盒向量。([GitHub][2])

---

## 7.4 Offload API

```text
POST /v1/offload/refs
GET  /v1/offload/refs/{ref_id}

POST /v1/offload/graph/update
GET  /v1/offload/graph/{session_id}

POST /v1/offload/restore
```

`restore` 请求示例：

```json
{
  "tenant_id": "tenant_001",
  "session_id": "session_001",
  "node_id": "N12",
  "result_ref": "ref_tool_abc"
}
```

响应：

```json
{
  "node": {
    "node_id": "N12",
    "title": "读取 TencentDB-Agent-Memory README"
  },
  "raw_content": "...完整工具结果...",
  "metadata": {}
}
```

---

## 7.5 Admin API

```text
POST /v1/admin/reindex
POST /v1/admin/compact
POST /v1/admin/export
POST /v1/admin/import
POST /v1/admin/delete-user
GET  /v1/admin/pipeline/status
GET  /v1/health
GET  /v1/metrics
```

`delete-user` 要做到：

```text
1. 删除 L0
2. 删除 L1
3. 删除 L2/L3
4. 删除 FTS index
5. 删除 vector index
6. 删除 offload refs
7. 写 audit log
```

SQLite FTS5 有 `secure-delete` 相关配置，官方文档说明它会实际删除旧全文索引条目，但会更慢；如果你有合规删除需求，SQLite 侧要特别处理 FTS 残留与 VACUUM。([SQLite 主页][6])

---

# 8. Recall 设计

不要只做 embedding。Tencent 的默认配置就是 hybrid，并支持 keyword、embedding、hybrid / RRF 融合；README 也明确提到 BM25 + 向量 + RRF。([GitHub][2])

推荐召回流程：

```text
before_recall(query):
  1. 读取 L3 persona
  2. 读取 L2 scene navigation
  3. query embedding
  4. L1 FTS search
  5. L1 vector search
  6. RRF 融合
  7. 加 priority / confidence / recency / type boost
  8. 截断到 token budget
  9. 返回 stable_context + dynamic_context
```

RRF 可以这样实现：

```python
def rrf_fuse(
    ranked_lists: list[list[str]],
    k: int = 60,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for results in ranked_lists:
        for rank, doc_id in enumerate(results, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores
```

然后再叠加业务分：

```python
final_score = (
    rrf_score
    + 0.05 * priority_boost
    + 0.03 * confidence_boost
    + 0.03 * recency_boost
    + type_boost
)
```

初期建议：

```yaml
recall:
  strategy: hybrid
  max_results: 5
  timeout_ms: 800
  score_threshold: 0.25
  token_budget: 1200
```

注意：召回是用户等待路径，必须有 timeout。超时就返回空记忆，不要阻塞 Agent 主流程。

---

# 9. Pipeline 设计

Pipeline 要分三种触发：

```text
1. every_n_conversations
2. idle_timeout
3. manual/admin trigger
```

建议初期配置：

```yaml
pipeline:
  every_n_conversations: 5
  enable_warmup: true
  warmup_steps: [1, 2, 4, 5]
  l1_idle_timeout_seconds: 600
  l2_delay_after_l1_seconds: 90
  l2_min_interval_seconds: 900
  l2_max_interval_seconds: 3600
  persona_trigger_every_n_memories: 50
```

Tencent 的配置里也有类似参数：`everyNConversations`、warm-up、`l1IdleTimeoutSeconds`、`l2MinIntervalSeconds`、`recall.timeoutMs`、`triggerEveryN` 等。([GitHub][10])

## 9.1 L0 Capture

```text
commit_turn:
  1. 校验 tenant/user/session
  2. 幂等检查
  3. 写 L0 原始事件
  4. 写 FTS index
  5. 如果支持 deferred embedding：
       先写 metadata + FTS
       后台补 embedding
     否则：
       同步 embedding + upsert
  6. notify pipeline
```

Tencent 源码里 SQLite 路径也有 deferred embedding 思路：先 metadata + FTS，后续后台补 L0 embedding，以避免 agent_end 被 embedding 请求拖慢。([GitHub][3])

## 9.2 L1 Extract

```text
L1 job:
  1. 从 checkpoint 之后读取 L0
  2. 拼 background context + new messages
  3. LLM JSON-mode 抽取 memory atoms
  4. 质量过滤
  5. 查相似 L1 作为冲突候选
  6. dedup / merge / update / insert
  7. 写 L1
  8. 更新 checkpoint
  9. 通知 L2
```

LLM 输出建议强制 JSON Schema：

```json
{
  "scenes": [
    {
      "scene_name": "agent-memory-system",
      "message_ids": ["evt_1", "evt_2"],
      "memories": [
        {
          "content": "用户希望将 TencentDB-Agent-Memory 复刻为 Python REST API。",
          "type": "project",
          "priority": 5,
          "confidence": 0.92,
          "source_event_ids": ["evt_1"],
          "metadata": {
            "language": "zh"
          }
        }
      ]
    }
  ]
}
```

## 9.3 L2 Scene

```text
L2 job:
  1. 找出最近变化的 L1
  2. 按 scene_name 聚合
  3. 读取已有 scene markdown
  4. LLM 增量更新 scene
  5. 更新 scene_index
  6. 生成 scene navigation
  7. 通知 L3
```

## 9.4 L3 Persona

```text
L3 job:
  1. 读取已有 persona
  2. 读取 scene navigation
  3. 读取最近变化的 scenes
  4. LLM 增量更新 persona
  5. 版本化保存
```

---

# 10. SQLite 与 Postgres 的具体取舍

## SQLite 系列

适合：

```text
- 本地开发
- 单用户 / 小团队
- 单机 Agent
- 边缘设备
- 私有化轻量部署
```

SQLite 初期实现建议：

```text
Keyword:
  SQLite FTS5

Vector:
  首选 sqlite-vec
  备选 embedding BLOB + Python cosine brute force

Concurrency:
  WAL
  单写多读
  API + worker 最好同进程，或者控制单 writer

Profile/Scene:
  DB 存一份
  可选 mirror 到 markdown 文件
```

SQLite FTS5 能通过虚拟表实现全文搜索，并用 `MATCH` 查询；其 `rank` 默认映射到 BM25，排序时使用 rank 通常比直接调用 bm25 更快。([SQLite 主页][6])

## Postgres 系列

适合：

```text
- 多用户
- 多 Agent
- 分布式 API + worker
- 生产环境
- 需要权限、审计、备份、迁移
```

Postgres 初期实现建议：

```text
Keyword:
  tsvector + GIN index + ts_rank_cd

Vector:
  pgvector
  小数据：exact search
  中大数据：HNSW
  超大批量导入后：IVFFlat 可选

Metadata:
  JSONB

Lock:
  pg_advisory_lock
  SELECT ... FOR UPDATE SKIP LOCKED

Jobs:
  pipeline_jobs 表 + worker pool
```

Postgres 官方文档说明全文搜索会把文档转成 `tsvector`，查询转成 `tsquery`，并可通过 `@@` 匹配；实际应用通常需要 GIN index 加速。排名可以用 `ts_rank` 或 `ts_rank_cd`，并且排名本身可以与业务因素如修改时间组合。([PostgreSQL][7])

pgvector 里 HNSW 查询性能通常比 IVFFlat 更好，但构建更慢、内存占用更高；IVFFlat 构建更快、内存更低，但 speed/recall tradeoff 较弱。([GitHub][8])

---

# 11. 部署形态

## 11.1 本地开发

```text
memory-api
  FastAPI
  SQLite
  in-process scheduler
  local file refs
```

```bash
uvicorn agent_memory_server.app.main:app --host 0.0.0.0 --port 8710
```

## 11.2 小型生产

```text
memory-api
memory-worker
Postgres + pgvector
Redis 可选
Object storage 可选
```

```text
┌─────────────┐       ┌──────────────┐
│ Agent App   │──────▶│ memory-api    │
└─────────────┘       └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │ Postgres      │
                      │ pgvector + FTS│
                      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │ memory-worker │
                      │ L1/L2/L3 jobs │
                      └──────────────┘
```

## 11.3 大型生产

```text
API 多副本
Worker 多副本
Postgres 主从 / 分区
对象存储保存大 refs
Prometheus + OpenTelemetry
admin console
```

---

# 12. 配置设计

```yaml
server:
  host: 0.0.0.0
  port: 8710
  auth:
    mode: api_key

store:
  backend: postgres  # sqlite | postgres
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
  model: bge-m3
  dimensions: 1024
  timeout_ms: 10000
  recall_timeout_ms: 1000
  capture_timeout_ms: 15000

llm:
  provider: openai_compatible
  base_url: https://api.example.com/v1
  api_key: ${LLM_API_KEY}
  model: deepseek-v3
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
  persona_trigger_every_n: 50

offload:
  enabled: true
  max_ref_chars_inline: 2000
  default_context_window: 200000
  mild_offload_ratio: 0.5
  aggressive_compress_ratio: 0.85
```

---

# 13. Agent 端集成方式

你的 Agent 主流程只需要两个强制调用和两个可选工具。

## 13.1 调 LLM 前

```python
recall = await memory_client.before_recall(
    tenant_id=tenant_id,
    user_id=user_id,
    agent_id="sales_agent",
    session_id=session_id,
    session_key=session_key,
    user_text=user_text,
)

messages = [
    {
        "role": "system",
        "content": base_system_prompt + "\n\n" + recall.stable_context,
    },
    *history,
    {
        "role": "user",
        "content": recall.dynamic_context + "\n\n" + user_text,
    },
]
```

## 13.2 调 LLM 后

```python
await memory_client.commit_turn(
    tenant_id=tenant_id,
    user_id=user_id,
    agent_id="sales_agent",
    session_id=session_id,
    session_key=session_key,
    idempotency_key=turn_id,
    messages=[
        {"role": "user", "content": user_text, "timestamp": user_ts},
        {"role": "assistant", "content": assistant_text, "timestamp": assistant_ts},
    ],
    tool_events=tool_events,
)
```

## 13.3 给 Agent 暴露工具

```python
tools = {
    "memory_search": memory_client.search_memories,
    "conversation_search": memory_client.search_conversations,
    "restore_memory_ref": memory_client.restore_ref,
}
```

这三个工具的意义不同：

```text
memory_search:
  查 L1 原子记忆

conversation_search:
  查 L0 原始证据

restore_memory_ref:
  查短期 offload 的工具原文
```

---

# 14. MVP 开发顺序

我建议你分 5 个版本做。

## V0.1：REST + L0 + SQLite

目标：先能可靠记录和查原始对话。

```text
- FastAPI
- MemoryCore skeleton
- SQLiteStore
- conversation_events
- FTS5
- /capture/turn
- /conversations/search
- /health
```

## V0.2：L1 + Hybrid Recall

目标：形成真正 agent memory。

```text
- L1 extractor
- memories 表
- memory_sources 表
- embedding service
- FTS + vector search
- RRF
- /recall/before
- /memories/search
```

## V0.3：Postgres 支持

目标：进入生产可用。

```text
- PostgresStore
- Alembic migrations
- pgvector
- tsvector + GIN
- JSONB metadata
- distributed job locks
```

## V0.4：L2/L3

目标：沉淀长期画像和场景。

```text
- scene_blocks
- persona_profiles
- scene extractor
- persona generator
- scene navigation
- profile editor API
```

## V0.5：Context Offload

目标：支持长任务工具日志压缩。

```text
- offload_refs
- offload_nodes
- offload_edges
- Mermaid builder
- restore endpoint
- tool result compression
```

---

# 15. 几个关键工程细节

## 15.1 不要让 L1/L2/L3 阻塞用户请求

`/capture/turn` 最多做：

```text
1. 写 L0
2. 写轻量索引
3. 通知 pipeline
4. 返回
```

L1/L2/L3 都交给 worker。

## 15.2 每条记忆必须可追溯

L1 必须带 `source_event_ids`。
L2 必须带 `source_memory_ids`。
L3 必须带 `source_scene_ids`。

否则一旦 persona 抽错，你无法纠错。

## 15.3 Prompt 注入要做预算

不要把所有召回结果塞进去。

```text
stable_context budget: 800-1500 tokens
dynamic_context budget: 800-1500 tokens
tool guide budget: 200-400 tokens
```

## 15.4 召回要支持降级

```text
embedding 挂了：
  fallback 到 FTS

FTS 不可用：
  fallback 到 vector

两者都不可用：
  返回 L3 persona + 最近 L1

数据库超时：
  返回空 recall，不影响主对话
```

这和 Tencent 的 store abstraction 精神一致：能力用 capabilities 表达，上层根据能力降级。([GitHub][5])

## 15.5 中文检索要单独处理

SQLite FTS5 默认 tokenizer 对中文不够友好。建议：

```text
SQLite:
  Python 侧 jieba 分词后写入 searchable_content

Postgres:
  初期用 simple config + 应用层分词
  后续可接中文分词扩展或专用检索服务
```

---

# 16. 版权和合规提醒

TencentDB-Agent-Memory 是 MIT License，允许使用、复制、修改、合并、发布、再许可和销售，但需要在软件副本或 substantial portions 中保留版权声明和许可声明。([GitHub][11])

所以你有两种安全做法：

```text
架构复刻：
  不复制源码，只复刻思想和接口，风险最低。

代码迁移：
  如果翻译或移植它的源码/Prompt/实现片段，需要保留 MIT license 和版权声明。
```

我建议你做“架构复刻 + 自己实现”，不要逐行翻译。

---

# 17. 最终建议

你的 Python REST 版可以命名成：

```text
AgentMemoryServer
```

核心定位：

```text
一个独立、可插拔、跨 Agent Runtime 的记忆中台。
```

最小闭环是：

```text
POST /v1/recall/before
  ↓
Agent 调 LLM
  ↓
POST /v1/capture/turn
  ↓
后台 L1/L2/L3 pipeline
  ↓
下一轮 recall 自动生效
```

初期技术栈建议：

```text
API:
  FastAPI + Pydantic

DB:
  SQLite: aiosqlite / SQLAlchemy + FTS5 + sqlite-vec optional
  Postgres: asyncpg / SQLAlchemy + pgvector + tsvector + JSONB

Migrations:
  Alembic

Worker:
  V0: in-process asyncio scheduler
  V1: standalone worker
  V2: Celery / Dramatiq / Arq + Redis or Postgres job table

Embedding:
  OpenAI-compatible endpoint abstraction

LLM:
  OpenAI-compatible JSON-mode abstraction

Observability:
  structured logs + Prometheus metrics + trace_id
```

一句话架构原则：

**L0 保证证据，L1 保证可检索事实，L2 保证长期场景，L3 保证稳定画像，Recall 保证低延迟注入，Pipeline 保证异步演化，Store Adapter 保证 SQLite/Postgres 可切换。**

[1]: https://raw.githubusercontent.com/Tencent/TencentDB-Agent-Memory/main/src/core/tdai-core.ts "raw.githubusercontent.com"
[2]: https://raw.githubusercontent.com/Tencent/TencentDB-Agent-Memory/main/README_CN.md "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/Tencent/TencentDB-Agent-Memory/main/src/core/hooks/auto-capture.ts "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/Tencent/TencentDB-Agent-Memory/main/src/core/record/l1-extractor.ts "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/Tencent/TencentDB-Agent-Memory/main/src/core/store/types.ts "raw.githubusercontent.com"
[6]: https://www.sqlite.org/fts5.html "SQLite FTS5 Extension"
[7]: https://www.postgresql.org/docs/current/textsearch-intro.html "PostgreSQL: Documentation: 18: 12.1. Introduction"
[8]: https://github.com/pgvector/pgvector "GitHub - pgvector/pgvector: Open-source vector similarity search for Postgres · GitHub"
[9]: https://www.postgresql.org/docs/current/datatype-json.html "PostgreSQL: Documentation: 18: 8.14. JSON Types"
[10]: https://raw.githubusercontent.com/Tencent/TencentDB-Agent-Memory/main/openclaw.plugin.json "raw.githubusercontent.com"
[11]: https://raw.githubusercontent.com/Tencent/TencentDB-Agent-Memory/main/LICENSE "raw.githubusercontent.com"
