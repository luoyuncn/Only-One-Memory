# Only-One-Memory

Only-One-Memory 是一个 Python 原生的 Agent Memory Runtime 框架，简称 **OOM**。名字灵感来自 Java 的 OOM 内存溢出：Agent 不应该把一切都塞进一次性上下文里撑爆自己，而应该把对话、事实、场景、画像和工具日志分层沉淀成可追溯的长期记忆。

当前项目处于设计落地阶段。完整设计见：[Only-One-Memory 设计](docs/superpowers/specs/2026-05-18-only-one-memory-design.md)。

## 项目定位

Only-One-Memory 不是一个简单的“记忆数据库”，而是一个面向 Agent 的独立记忆运行时：

- **REST-first**：Python Agent、飞书机器人、MCP Agent、LangGraph、CrewAI 和自研 Runtime 都能通过 HTTP/SDK 接入。
- **Python-native**：核心计划使用 FastAPI、Pydantic、SQLAlchemy/Alembic 和 asyncio worker。
- **高保真复刻 TencentDB-Agent-Memory**：对齐 `TdaiCore`、L0/L1/L2/L3、Hybrid Recall、异步 Pipeline、Context Offload 和核心提示词体系。
- **Store-agnostic**：一期即支持 SQLite/sqlite-vec 和 Postgres/pgvector，后续可扩展更多向量或检索后端。
- **Evidence-first**：所有高层记忆都能追溯到原始 L0 证据。

## 记忆分层

```text
L0 Conversation   原始对话、工具调用、工具结果、运行事件
      ↓
L1 Atom           结构化原子记忆：persona / episodic / instruction
      ↓
L2 Scenario       场景块：长期项目、生活主题、任务背景、叙事文档
      ↓
L3 Persona        稳定画像：长期偏好、交互协议、认知模式、工作方式
```

短期上下文则通过 Context Offload 处理：

```text
refs 原文
  -> tool pair summary / jsonl
  -> Mermaid task graph
  -> node_id / result_ref 下钻恢复
```

## 核心架构

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
           SQLite/sqlite-vec / Postgres/pgvector
        -> Storage + Index
```

`MemoryCore` 是唯一稳定业务入口，类似 TencentDB-Agent-Memory 中的 `TdaiCore`。FastAPI 只做协议适配，不承载核心记忆逻辑。

## 主要能力

- **L0 Capture**：记录 user/assistant/tool/system/event 原始事件，支持幂等写入。
- **L1 Extraction**：从 L0 中抽取原子记忆，并进行冲突检测、去重、merge/update/skip。
- **L2 Scene**：把 L1 记忆整合为可读、可编辑、可追溯的 Markdown 场景块。
- **L3 Persona**：生成和维护稳定用户画像，并附带 scene navigation。
- **Hybrid Recall**：FTS + Vector + RRF 融合召回，叠加 priority、confidence、recency 等业务分。
- **Store Adapter**：通过 capability flags 在 SQLite/sqlite-vec 与 Postgres/pgvector 之间切换和降级。
- **Async Pipeline**：L1/L2/L3 异步演化，避免阻塞主对话。
- **Context Offload**：将长工具日志卸载到 refs，用 Mermaid 图谱和 node_id/result_ref 支持恢复。
- **Prompt Fidelity**：尽量直接翻译/复用 TencentDB-Agent-Memory 的核心 prompt，并保留 MIT attribution。

## 计划 API

Agent 主流程：

```text
POST /v1/recall/before
POST /v1/capture/turn
POST /v1/sessions/{session_key}/end
```

Agent 工具：

```text
POST /v1/memories/search
POST /v1/conversations/search
POST /v1/offload/restore
```

管理接口：

```text
GET    /v1/scenes
PATCH  /v1/scenes/{scene_id}
GET    /v1/profiles/{scope}/{scope_id}
PATCH  /v1/profiles/{scope}/{scope_id}
GET    /v1/admin/pipeline/status
POST   /v1/admin/reindex
DELETE /v1/admin/users/{user_id}
GET    /v1/health
GET    /v1/metrics
```

## 一期范围

V0.1 的目标不是只做 SQLite 本地 MVP，而是直接建立双后端基础能力：

- FastAPI skeleton
- `MemoryCore` lifecycle
- 配置系统
- SQLite schema + FTS5 + sqlite-vec
- Postgres schema + JSONB + tsvector/GIN + pgvector
- store backend selection
- `/v1/capture/turn`
- `/v1/conversations/search`
- `/v1/health`
- capture 幂等
- SQLite/Postgres migration smoke tests

## 路线图

```text
V0.1  REST + MemoryCore + SQLite/Postgres L0
V0.2  L1 + Hybrid Recall
V0.3  Pipeline 完整化 + Worker 化
V0.4  L2/L3 Scene + Persona
V0.5  Context Offload
V0.6  Production Hardening
```

首个可运行闭环是 V0.1；首个真正具备长期记忆能力的闭环是 V0.2；接近 TencentDB-Agent-Memory 完整能力的版本是 V0.5。

## 参考与许可

本项目的架构和提示词设计参考并计划高保真复刻 [TencentDB-Agent-Memory](https://github.com/Tencent/TencentDB-Agent-Memory) 的核心思想。TencentDB-Agent-Memory 使用 MIT License；本项目复用或翻译其 prompt/design 时会保留来源说明和 license notices。

Only-One-Memory 本身使用 MIT License，详见 [LICENSE](LICENSE)。
