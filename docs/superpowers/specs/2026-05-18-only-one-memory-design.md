# Only-One-Memory Design

Date: 2026-05-18

## 1. Goal

Only-One-Memory is a Python-native Agent Memory Runtime. It should reproduce the core architecture and behavior of TencentDB-Agent-Memory as closely as practical, while exposing a REST-first interface suitable for Python agents, Feishu bots, MCP agents, LangGraph, CrewAI, and custom runtimes.

The project is not a direct Node sidecar wrapper. It is a high-fidelity Python reimplementation of the memory runtime:

- `TdaiCore` becomes `MemoryCore`.
- OpenClaw hooks become FastAPI endpoints and a Python SDK.
- `IMemoryStore` becomes a Python `MemoryStore` protocol with runtime capabilities.
- TencentDB-Agent-Memory prompts are translated or reused as directly as possible under the MIT license, with attribution.
- Implementation is staged, but the code design covers the full system.

Core principles:

- L0 preserves raw evidence.
- L1 stores atomic, searchable memories.
- L2 consolidates memories into scene blocks.
- L3 maintains stable persona/profile context.
- Recall injects low-latency stable and dynamic context.
- Pipeline work evolves memory asynchronously.
- Store adapters keep SQLite and Postgres interchangeable.
- Context offload compresses long-running tool logs without losing traceability.

## 2. Reference System

The design is based on the local reference repository:

`D:\dev\agent\TencentDB-Agent-Memory`

Important source files:

- `src/core/tdai-core.ts`: host-neutral facade for recall, capture, search, and pipeline management.
- `src/core/store/types.ts`: backend-agnostic store interface and capability flags.
- `src/core/hooks/auto-capture.ts`: L0 capture and deferred embedding behavior.
- `src/core/hooks/auto-recall.ts`: hybrid recall, stable/dynamic context split, timeout behavior.
- `src/utils/pipeline-manager.ts`: L0 -> L1 -> L2 -> L3 pipeline scheduling.
- `src/core/prompts/l1-extraction.ts`: L1 scene segmentation and memory extraction prompt.
- `src/core/prompts/l1-dedup.ts`: L1 conflict detection and merge prompt.
- `src/core/prompts/scene-extraction.ts`: L2 scene block prompt and file operation rules.
- `src/core/prompts/persona-generation.ts`: L3 persona prompt and persona file constraints.
- `src/offload/*`: context offload, refs, Mermaid, and compression behavior.

## 3. Licensing And Prompt Reuse

TencentDB-Agent-Memory is MIT licensed. This project may translate and reuse prompt content and design structure, provided attribution and license notices are retained.

Required files:

- `docs/attribution/tencentdb-agent-memory.md`
- `NOTICE` or a README attribution section
- `memory_core/prompts/attribution.py`

Attribution text should state that portions of the prompt design and memory architecture are adapted from TencentDB-Agent-Memory under the MIT license.

Prompt modules should keep source mapping comments, for example:

```python
# Adapted from TencentDB-Agent-Memory:
# src/core/prompts/l1-extraction.ts
# License: MIT
```

## 4. Architecture

Runtime shape:

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

`MemoryCore` is the stable business entry point. API routes, SDKs, CLIs, workers, and future MCP adapters should call `MemoryCore` instead of directly using stores or services.

FastAPI is an adapter only. It validates HTTP payloads, resolves dependencies, and maps HTTP errors, but it does not own memory behavior.

## 5. Proposed Directory Structure

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
  pyproject.toml
```

## 6. MemoryCore

`MemoryCore` mirrors TencentDB-Agent-Memory's `TdaiCore`.

Public methods:

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

Internal state:

- config
- logger
- store
- embedding service
- LLM runner factory
- pipeline manager
- store readiness gate
- scheduler start gate
- background task registry

Execution chain:

```text
POST /v1/recall/before
  -> BeforeRecallRequest
  -> MemoryCore.before_recall()
  -> recall.auto_recall()
  -> L3 persona + L2 scene navigation + L1 hybrid search
  -> stable_context + dynamic_context

Agent calls the LLM

POST /v1/capture/turn
  -> CompletedTurn
  -> MemoryCore.commit_turn()
  -> capture.l0_recorder
  -> store.upsert_l0
  -> pipeline.notify_conversation
  -> quick response

Background pipeline:
  L1 extract/dedup/write
  -> L2 scene update
  -> L3 persona update
```

Important semantics:

- `before_recall()` is user-facing and must have a timeout.
- `commit_turn()` records L0 and notifies the pipeline; it does not synchronously run L1/L2/L3.
- `end_session()` flushes only the named session. It must not destroy global scheduler state.
- `shutdown()` drains background tasks, flushes pending work within a bounded timeout, and closes stores.

## 7. Domain Models

Common identity fields should be present in request models and persisted records:

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

For high fidelity with Tencent prompts, the initial L1 types are:

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

## 8. Database Schema

Logical tables:

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

Required traceability:

- `memory_sources`: L1 -> L0 evidence
- `scene_sources`: L2 -> L1 evidence
- `persona_sources`: L3 -> L2 evidence
- offload refs can be referenced by L0 tool events and offload graph nodes

Indexes:

```text
L0:
  session_key + recorded_at
  tenant_id + user_id + event_ts
  FTS index(content/searchable_content)
  optional vector index

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

SQLite:

- FTS5 for keyword search.
- Embedding stored as BLOB or JSON initially.
- Python brute-force cosine as the default vector fallback.
- Optional sqlite-vec later.
- WAL mode.
- In-process worker first.

Postgres:

- JSONB metadata.
- tsvector + GIN.
- pgvector.
- `SELECT ... FOR UPDATE SKIP LOCKED` for DB-backed workers.
- advisory locks or job-table locks for distributed safety.

## 9. REST API And SDK

Main flow:

```text
POST /v1/recall/before
POST /v1/capture/turn
POST /v1/sessions/{session_key}/end
```

Search and tool flow:

```text
POST /v1/memories/search
POST /v1/conversations/search
POST /v1/offload/restore
```

Management flow:

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

Python SDK shape:

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

Security:

- V0 uses API key auth.
- V1 adds tenant-scoped API keys.
- V2 may add JWT/OIDC.
- `trace_id` is propagated.
- `/v1/capture/turn` requires an `idempotency_key`.
- Recall/search failures degrade to empty results; capture persistence failures return errors.

## 10. Store Adapter

`MemoryStore` mirrors Tencent's `IMemoryStore`.

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

Rules:

- Store methods used by recall should fail closed with empty results or `False` plus logs.
- Admin and migration methods may raise explicit errors.
- Capabilities represent runtime reality, not configuration intent.
- Embedding provider/model/dimension changes should produce `needs_reindex=True`.

## 11. Recall And Search

Recall mirrors Tencent's auto-recall:

```text
1. Clean user_text.
2. Prepare L3 persona, L2 scene navigation, and L1 hybrid search.
3. Use native hybrid if the store supports it.
4. Otherwise run FTS and vector search, then RRF merge.
5. Apply secondary boosts.
6. Truncate by token budget.
7. Return stable_context and dynamic_context.
```

Context split:

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

RRF:

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

Boosts:

```text
final_score =
  rrf_score
  + priority_boost
  + confidence_boost
  + recency_boost
  + type_boost
```

Default config:

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

Search tools:

- `/v1/memories/search` searches L1 structured memories.
- `/v1/conversations/search` searches L0 raw evidence.

Both should return Agent-readable text and structured JSON fields.

## 12. Capture And Pipeline

Capture flow:

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

Idempotency:

```text
idempotency_records:
  tenant_id
  idempotency_key
  request_hash
  response_json
  created_at
  expires_at
```

Same key and same hash returns cached response. Same key and different hash returns conflict.

Pipeline triggers:

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

Pipeline state:

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

V0 uses in-process asyncio queues. V1 adds DB-backed `pipeline_jobs` and a separate worker process.

## 13. Prompt System

Prompt modules are first-class code with source attribution, parser tests, and schema validation.

### L1 Extraction

Adapted from `src/core/prompts/l1-extraction.ts`.

Inputs:

- `previous_scene_name`
- `background_messages`: context only; do not extract from these
- `new_messages`: extract only from these

Output:

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

Parser must handle markdown fences, extra text, control characters, missing metadata, empty memories, and invalid types.

### L1 Dedup

Adapted from `src/core/prompts/l1-dedup.ts`.

Actions:

- `store`
- `update`
- `skip`
- `merge`

Dedup candidate retrieval:

- vector top-K when available
- FTS top-K fallback
- skip dedup and store all when neither is available

### L2 Scene

Adapted from `src/core/prompts/scene-extraction.ts`.

The prompt semantics should remain close to Tencent's version: scene files are Markdown narrative documents, not flat lists; the LLM can read/write/edit scene files; deletion is represented by `[DELETED]`.

Python should not let the LLM touch the real file system directly. It should use a controlled tool runner:

```text
SceneToolRunner:
  read_scene(filename)
  write_scene(filename, content)
  edit_scene(filename, edits)
  delete_scene(filename)
```

Enforced constraints:

- no path traversal
- read whitelist from existing scene file list
- only `.md` scene files
- delete maps to `[DELETED]`
- engineering side syncs scene index

Scene Markdown format:

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

Adapted from `src/core/prompts/persona-generation.ts`.

Inputs:

- `mode`: `first` or `incremental`
- `current_time`
- `total_processed`
- `scene_count`
- `changed_scene_count`
- `changed_scenes_content`
- `existing_persona`
- `trigger_info`

Python uses a controlled persona runner:

```text
PersonaToolRunner:
  write_persona(content)
  edit_persona(edits)
```

Constraints:

- only `persona.md`
- no scene file reads
- no scene navigation in model output
- persona body length target is 2000 characters or less
- engineering appends scene navigation after generation

## 14. Context Offload

Offload mirrors Tencent's short-term symbolic memory.

Tables:

```text
offload_refs
offload_entries
offload_nodes
offload_edges
```

REST API:

```text
POST /v1/offload/refs
GET  /v1/offload/refs/{ref_id}

POST /v1/offload/entries
GET  /v1/offload/entries?session_id=...

POST /v1/offload/graph/update
GET  /v1/offload/graph/{session_id}

POST /v1/offload/restore
```

Layering:

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

Implementation phases:

- V0.5a: refs + restore API
- V0.5b: tool pair summary + offload entries
- V0.5c: Mermaid graph generation
- V0.5d: compressor policy + SDK helper

## 15. Configuration

Initial config shape:

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
    vector_backend: blob_bruteforce
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

## 16. Testing Strategy

Unit tests:

- config validation
- Pydantic schemas
- store init/upsert/query/search
- RRF and scoring
- recall timeout fallback
- capture idempotency
- deferred embedding registry

Prompt/parser tests:

- L1 extraction JSON parsing
- L1 dedup decisions
- hallucinated record IDs
- scene tool sandbox
- persona tool sandbox

Pipeline tests:

- threshold trigger
- warmup progression
- idle timeout
- L1 retry
- L2 delay/min/max interval
- L3 pending rerun
- session-end scoped flush
- shutdown background drain

API tests:

- `/health`
- cold-start `/v1/recall/before`
- `/v1/capture/turn`
- `/v1/memories/search`
- `/v1/conversations/search`
- `/v1/admin/pipeline/status`
- user deletion

Integration tests:

- capture turns -> run L1 -> search -> run L2 -> run L3 -> recall
- embedding disabled -> FTS fallback
- FTS unavailable -> vector fallback
- restart -> checkpoint restore

Quality gates:

- ruff
- mypy or pyright
- pytest
- migration smoke tests
- OpenAPI generation check

## 17. Implementation Plan

### V0.1 REST + MemoryCore + SQLite L0

- FastAPI skeleton
- `MemoryCore` lifecycle
- config
- SQLite basic schema
- `/v1/capture/turn`
- `/v1/conversations/search` via FTS
- `/v1/health`
- idempotency
- tests

### V0.2 L1 + Hybrid Recall

- prompt migration: L1 extraction and dedup
- L1 extractor
- MemoryAtom store
- embedding provider
- RRF
- `/v1/recall/before`
- `/v1/memories/search`
- pipeline L1 threshold and idle
- tests

### V0.3 Pipeline Completion + Postgres

- warmup, L2, L3 queues
- checkpoint restore
- PostgresStore
- pgvector + tsvector
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

### V0.6 Production Hardening

- auth scopes
- audit/export/import/delete-user
- metrics
- migration tooling
- Docker

## 18. Success Criteria

V0.1 is successful when a Python agent can record turns through REST and search raw conversations after restart.

V0.2 is successful when captured turns can produce L1 memories and the next recall call returns stable and dynamic context.

V0.4 is successful when L1 memories evolve into scene blocks and a persona profile, with traceability back to L0 evidence.

V0.5 is successful when long tool outputs can be offloaded to refs, summarized into graph nodes, restored by `node_id` or `result_ref`, and used by an Agent without losing raw evidence.

## 19. Self-Review

Completeness scan: no unresolved markers or undefined sections remain.

Consistency check: the architecture consistently routes behavior through `MemoryCore`, keeps FastAPI as an adapter, and preserves L0/L1/L2/L3 traceability.

Scope check: this is a full-system design but implementation is explicitly staged. V0.1 and V0.2 are small enough for separate implementation plans.

Ambiguity check: prompt reuse is explicitly MIT-attributed and high fidelity; L1 types are intentionally limited to Tencent's initial `persona`, `episodic`, and `instruction` categories for compatibility.
