<div align="center">

<img src="./assets/images/oom-logo.svg" alt="Only-One-Memory" width="880" />

### 别让 Agent 把上下文撑爆，把该记的沉淀为可追溯长期记忆。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Status](https://img.shields.io/badge/status-design%20landing-orange)](#-当前状态)
[![Python Native](https://img.shields.io/badge/Python-native-3776AB?logo=python&logoColor=white)](#-项目定位)
[![REST First](https://img.shields.io/badge/REST-first-0284C7)](#-计划-api)
[![Store Agnostic](https://img.shields.io/badge/store-SQLite%20%2F%20Postgres-7C3AED)](#-store-agnostic)
[![Evidence First](https://img.shields.io/badge/evidence-first-0F766E)](#-方案特点)

[设计亮点](#-设计亮点) · [项目简介](#项目简介) · [核心技术](#核心技术从上下文堆砌到可追溯记忆-runtime) · [快速开始](#快速开始) · [计划 API](#-计划-api) · [路线图](#-路线图)

---

</div>

## ✨ 设计亮点

> **Only-One-Memory = Evidence-first 长期记忆 + REST-first Agent Memory Runtime。**
>
> OOM 的目标不是把所有历史都塞进上下文，也不是把所有信息压成不可逆摘要；而是把对话、事实、场景、画像和工具日志分层沉淀，让 Agent 既能“想得起”，也能“查得到”。

| 记忆问题 | OOM 的设计方案 | 目标版本 |
| :--- | :--- | :---: |
| 上下文越堆越爆 | 用 `Context Offload` 将厚重工具日志卸载到 refs，只把 Mermaid 任务图注入上下文 | V0.5 |
| 长期偏好难复用 | 用 L0 → L1 → L2 → L3 将碎片对话提炼为场景与画像 | V0.2+ |
| 向量召回像黑盒 | FTS + Vector + RRF 融合召回，再叠加 priority / confidence / recency | V0.2 |
| 摘要丢证据 | 所有高层记忆保留 `evidence_ref`，可下钻回 L0 原始事件 | V0.2+ |
| Agent 框架难接入 | REST-first + Python SDK，适配 Bot、MCP、LangGraph、CrewAI 与自研 Runtime | V0.1+ |
| 存储后端被锁死 | SQLite/sqlite-vec 与 Postgres/pgvector 双后端，后续可扩展更多 Store Adapter | V0.1 |

---

## 当前状态

Only-One-Memory 当前处于 **设计落地阶段**。首个可运行闭环目标是 V0.1：建立 REST 服务、`MemoryCore` 生命周期、SQLite/Postgres L0 采集与基础检索。

完整设计见：[Only-One-Memory 设计](docs/superpowers/specs/2026-05-18-only-one-memory-design.md)。

---

## 项目简介

**Only-One-Memory 是一个 Python 原生的 Agent Memory Runtime 框架，简称 OOM。**

名字灵感来自 Java 的 OOM 内存溢出：Agent 不应该把一切都塞进一次性上下文里撑爆自己，而应该把信息分层沉淀成可追溯、可检索、可编辑、可演化的长期记忆。

OOM 不是一个简单的“记忆数据库”。它更像是独立运行在 Agent 外部的记忆操作系统：

- **记录原文**：捕获 user / assistant / tool / system / event 原始事件。
- **提炼事实**：把原始对话转为 L1 原子记忆，并进行去重、冲突检测和合并。
- **组织场景**：把分散事实整合成可读的 Markdown 场景块。
- **维护画像**：生成稳定的用户画像、长期偏好、交互协议和工作方式。
- **混合召回**：在对话前根据当前任务召回高价值记忆。
- **保留证据**：高层记忆不是黑盒摘要，而是能回到 L0 证据。

> **让 Agent 记住该记的，让上下文只承载当下真正需要的。**

---

## 项目定位

Only-One-Memory 面向的是需要长期运行、跨会话复用经验、并且需要可追溯证据链的 Agent 系统。

| 定位 | 说明 |
| :--- | :--- |
| **REST-first** | Python Agent、飞书机器人、MCP Agent、LangGraph、CrewAI 和自研 Runtime 都能通过 HTTP/SDK 接入。 |
| **Python-native** | 核心计划使用 FastAPI、Pydantic、SQLAlchemy/Alembic 和 asyncio worker。 |
| **MemoryCore-first** | `MemoryCore` 是唯一稳定业务入口；FastAPI 只做协议适配，不承载核心记忆逻辑。 |
| **Store-agnostic** | 一期即支持 SQLite/sqlite-vec 与 Postgres/pgvector，后续可扩展更多向量或检索后端。 |
| **Evidence-first** | 所有高层记忆都能追溯到原始 L0 证据。 |
| **Prompt Fidelity** | 尽量对齐 TencentDB-Agent-Memory 的核心 prompt / design，并保留 MIT attribution。 |

---

## 核心技术：从上下文堆砌到可追溯记忆 Runtime

### 1. MemoryCore：唯一稳定业务入口

OOM 的核心不是某个数据库表，也不是某个 API handler，而是 `MemoryCore`。

<p align="center">
  <img src="./assets/images/oom-architecture.svg" alt="Only-One-Memory Architecture" width="920" />
</p>

`MemoryCore` 负责串联捕获、提取、场景归纳、画像维护、召回、搜索、上下文卸载和管理操作。外层的 FastAPI、SDK、Bot Adapter 或 MCP 工具只负责协议适配。

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

这种拆分让 OOM 可以独立于任意 Agent 框架演化：Agent 换了，记忆不必重写；存储换了，业务入口也不必重写。

---

### 2. 记忆分层：L0 → L1 → L2 → L3

传统记忆系统容易把所有历史切片后平铺进向量库。OOM 选择更接近“语义金字塔”的方式：底层保存事实证据，高层保存结构与方向。

<p align="center">
  <img src="./assets/images/oom-memory-pyramid.svg" alt="Only-One-Memory L0 to L3 semantic pyramid" width="920" />
</p>

```text
L0 Conversation   原始对话、工具调用、工具结果、运行事件
      ↓
L1 Atom           结构化原子记忆：persona / episodic / instruction
      ↓
L2 Scenario       场景块：长期项目、生活主题、任务背景、叙事文档
      ↓
L3 Persona        稳定画像：长期偏好、交互协议、认知模式、工作方式
```

| 层级 | 内容 | 作用 | 典型存储 |
| :--- | :--- | :--- | :--- |
| **L0 Conversation** | 原始事件、工具调用、工具结果、运行事件 | 保留证据与可恢复原文 | DB / archive |
| **L1 Atom** | persona / episodic / instruction 原子记忆 | 可检索、可去重、可冲突检测的事实单元 | DB + FTS + Vector |
| **L2 Scenario** | 项目、生活主题、长期任务背景 | 把事实组织成可读上下文 | Markdown / DB |
| **L3 Persona** | 长期偏好、交互协议、稳定画像 | 提供高层理解和召回导航 | Markdown / DB |

上层用于“理解”，下层用于“考证”。当 Agent 需要快速判断用户偏好时，可以优先看 L3；当它需要精确事实时，可以沿 L3 → L2 → L1 → L0 下钻。

---

### 3. Evidence-first：抽象不等于丢证据

OOM 的核心原则是：**任何高层记忆都必须能回到原始证据。**

<p align="center">
  <img src="./assets/images/oom-drilldown-chain.svg" alt="Only-One-Memory Drill Down Chain" width="920" />
</p>

```text
L3 Persona / L2 Scenario / L1 Atom
        -> evidence_ref / source_event_ids / result_ref
        -> L0 Conversation / refs 原文
```

这意味着：

- L2 场景块不是不可逆摘要，而是带来源索引的 Markdown 结构。
- L3 用户画像不是“凭感觉写的 persona”，而是可以追溯到相关场景和原子记忆。
- 工具日志被卸载后，仍然可以通过 `node_id` / `result_ref` 恢复原文。
- 召回错了可以调试，记忆过期了可以修订，冲突出现了可以定位证据。

---

### 4. Hybrid Recall：关键词、语义与业务分融合

OOM 的召回不是只依赖向量相似度，而是计划使用多路召回与融合排序：

```text
Query
  -> FTS keyword search
  -> Vector semantic search
  -> RRF rank fusion
  -> business scoring
     priority + confidence + recency + scope + memory_type
  -> final memory pack
```

| 召回信号 | 解决的问题 |
| :--- | :--- |
| **FTS** | 精确项目名、人名、工具名、日期、错误码等关键词。 |
| **Vector** | 语义相近但措辞不同的偏好、场景和任务背景。 |
| **RRF** | 将多路排序合并，降低单一路径误召回风险。 |
| **Business Score** | 结合优先级、置信度、时间衰减和作用域，让召回更贴近任务。 |

---

### 5. Context Offload：让长任务折叠成可恢复符号

短期上下文不应该被几十万 Token 的搜索结果、报错日志和工具输出淹没。OOM 计划用 Context Offload 把厚重信息卸载到外部 refs，只把轻量结构留在上下文。

```text
refs 原文
  -> tool pair summary / jsonl
  -> Mermaid task graph
  -> node_id / result_ref 下钻恢复
```

```mermaid
graph LR
    Log["繁杂冗长的工具日志"] -->|1. 保存原文| Refs[(refs / archive)]
    Log -->|2. 提取步骤摘要| Jsonl[summary.jsonl]
    Jsonl -->|3. 生成拓扑结构| MMD[Mermaid task graph]
    MMD -->|4. 轻量注入| Agent((Agent Context))
    Agent -.->|按 node_id / result_ref 恢复| Refs
```

Agent 在上下文中看到的是任务图，而不是全部日志；需要核查细节时再按引用下钻。这让上下文更清爽，也让每次压缩仍然可恢复。

---

## Store-agnostic

OOM 从 V0.1 开始就计划建设双后端能力，而不是先做单一 SQLite MVP。

| 后端 | 关键词检索 | 向量检索 | 结构化能力 | 适用场景 |
| :--- | :--- | :--- | :--- | :--- |
| **SQLite** | FTS5 | sqlite-vec | JSON / 本地文件 | 本地开发、单机 Bot、个人 Agent。 |
| **Postgres** | tsvector / GIN | pgvector | JSONB / 事务能力 | 多用户服务、生产部署、团队 Agent。 |

Store Adapter 会通过 capability flags 暴露后端能力。当某个后端不支持特定能力时，OOM 应该能显式降级，而不是悄悄失败。

```text
StoreAdapter.capabilities:
  - supports_fts
  - supports_vector
  - supports_jsonb
  - supports_hybrid_recall
  - supports_migration
```

---

## 快速开始

> 当前项目还在设计落地阶段。下面给出的是 V0.1 目标开发/接入形态，具体命令会随着实现更新。

### 1. 克隆项目

```bash
git clone https://github.com/luoyuncn/Only-One-Memory.git
cd Only-One-Memory
```

### 2. 阅读设计文档

```bash
open docs/superpowers/specs/2026-05-18-only-one-memory-design.md
```

### 3. V0.1 目标启动方式

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"

# SQLite 本地后端
export OOM_STORE_BACKEND=sqlite
export OOM_SQLITE_PATH=.oom/oom.db

# 启动 API
uvicorn only_one_memory.api:app --reload
```

### 4. 健康检查

```bash
curl http://localhost:8000/v1/health
```

### 5. 捕获一轮对话

```bash
curl -X POST http://localhost:8000/v1/capture/turn \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "session_key": "demo-session",
    "turn_id": "turn-001",
    "messages": [
      {"role": "user", "content": "以后回答我尽量给出可执行步骤。"},
      {"role": "assistant", "content": "好的，我会优先给出可执行步骤。"}
    ]
  }'
```

---

## V0.1 Postgres 初始化与 FAQ

### 最小环境变量

远程 Postgres 默认目标数据库名为 `oom`。复制 `.env.example` 到 `.env`，然后替换账号、密码和主机：

```env
OOM_STORE_BACKEND=postgres
OOM_POSTGRES_DSN=postgresql+asyncpg://user:password@host:5432/oom
```

如果 `OOM_POSTGRES_DSN` 中的用户不能创建数据库，可以额外配置管理员连接串：

```env
OOM_POSTGRES_ADMIN_DSN=postgresql+asyncpg://admin:password@host:5432/postgres
```

### 初始化数据库与 V0.1 schema

```bash
uv sync
uv run python scripts/init_postgres.py
```

脚本会读取 `.env`，连接同一远程实例的维护库 `postgres`，在缺失时创建 `oom` 数据库，然后连接 `oom` 业务库执行 `CREATE EXTENSION IF NOT EXISTS vector`，并初始化 V0.1 表结构与索引。

### 远程 Postgres 部署检查清单

1. **网络可达**：远程数据库安全组、防火墙、白名单允许当前机器访问数据库端口，通常是 `5432`。
2. **连接串正确**：`OOM_POSTGRES_DSN` 指向业务数据库，默认库名为 `oom`，不是默认维护库 `postgres`。
3. **数据库存在**：脚本可以创建 `oom`；如果业务账号没有建库权限，使用 `OOM_POSTGRES_ADMIN_DSN` 或让管理员提前创建。
4. **pgvector 已安装**：服务器或云数据库实例必须支持 `pgvector`，否则 `CREATE EXTENSION vector` 无法执行。
5. **业务库已启用 vector**：扩展是 database-scoped；即使默认数据库已经启用，也仍需在 `oom` 业务库中启用。
6. **账号权限足够**：创建 `vector` 扩展可能要求 superuser、云厂商的高权限账号，或由控制台/管理员代为启用。
7. **初始化脚本完成**：脚本需要成功创建表、GIN 索引和向量字段。
8. **V0.1 功能验证通过**：至少跑通 Postgres L0 存储测试和捕获搜索 API 测试。

可用 SQL 预检：

```sql
-- 在 oom 业务库执行：确认服务器是否提供 pgvector
SELECT * FROM pg_available_extensions WHERE name = 'vector';

-- 在 oom 业务库执行：确认当前业务库是否已经启用 vector
SELECT * FROM pg_extension WHERE extname = 'vector';

-- 在 oom 业务库执行：如果有权限，手动启用
CREATE EXTENSION IF NOT EXISTS vector;
```

### 主测 V0.1 功能

```bash
uv run pytest tests/integration/test_postgres_l0_store.py -q
uv run pytest tests/integration/test_capture_and_search_api.py -q
uv run pytest -q
```

### FAQ

**Q: `ModuleNotFoundError: No module named 'oom'` 是什么？**

A: 直接执行脚本时如果项目根目录不在 Python import path，会找不到 `oom` 包。当前脚本已在入口处自动加入项目根目录；推荐使用：

```bash
uv run python scripts/init_postgres.py
```

**Q: `InsufficientPrivilegeError: permission denied to create database` 是什么？**

A: 连接已经成功，但 `OOM_POSTGRES_DSN` 里的用户没有 `CREATE DATABASE` 权限。处理方式三选一：

- 给该用户授予 `CREATEDB`。
- 让管理员先手动创建 `oom` 数据库。
- 在 `.env` 中配置 `OOM_POSTGRES_ADMIN_DSN`，用有权限的账号负责建库。

**Q: `extension "vector" is not available` 是什么？**

A: 脚本会在 `OOM_POSTGRES_DSN` 指向的业务数据库中执行 `CREATE EXTENSION IF NOT EXISTS vector`。如果仍然看到这个错误，说明远程 PostgreSQL 服务器没有安装 `pgvector` 扩展。`CREATE EXTENSION vector` 只能启用服务器已安装的扩展，不能安装系统包。

可先在目标库检查：

```sql
SELECT * FROM pg_available_extensions WHERE name = 'vector';
```

如果没有结果：

- 自建 PostgreSQL：需要在服务器上安装与 PostgreSQL 版本匹配的 pgvector 包。
- 云数据库：需要确认服务商和当前套餐是否支持 pgvector，并按控制台或管理员流程开启。

V0.1 的 Postgres 后端当前依赖 `pgvector`；如果远程库不支持 pgvector，可以先用 SQLite 后端测试，或后续实现 Postgres 无向量降级模式。

**Q: `permission denied to create extension "vector"` / `Must be superuser to create this extension` 是什么？**

A: 这说明远程 PostgreSQL 已经识别到 `vector` 扩展，但当前连接到 `oom` 业务库的用户没有权限启用它。注意：扩展需要在每个业务数据库中单独启用；“默认数据库已经启用”不代表 `oom` 已启用。

处理方式：

- 让 DBA 或云数据库管理员连接 `oom` 业务库执行 `CREATE EXTENSION IF NOT EXISTS vector;`。
- 如果云厂商提供扩展管理控制台，在控制台为 `oom` 数据库启用 pgvector/vector。
- 换用具有启用扩展权限的 DSN 运行初始化脚本。
- 启用后再用业务账号运行 `uv run python scripts/init_postgres.py`，脚本会继续初始化 V0.1 schema。

**Q: 数据库已经创建了，还需要跑初始化脚本吗？**

A: 需要。脚本会跳过已存在的数据库，但仍会初始化 V0.1 schema，包括 `conversation_events`、FTS 索引和向量字段。

---

## 🧩 计划 API

### Agent 主流程

```text
POST /v1/recall/before
POST /v1/capture/turn
POST /v1/sessions/{session_key}/end
```

| API | 用途 |
| :--- | :--- |
| `POST /v1/recall/before` | 在 Agent 回复前召回相关长期记忆与当前任务上下文。 |
| `POST /v1/capture/turn` | 捕获一轮对话、工具调用和运行事件，写入 L0。 |
| `POST /v1/sessions/{session_key}/end` | 标记会话结束，触发或调度异步记忆演化。 |

### Agent 工具

```text
POST /v1/memories/search
POST /v1/conversations/search
POST /v1/offload/restore
```

| API | 用途 |
| :--- | :--- |
| `POST /v1/memories/search` | 搜索 L1/L2/L3 记忆。 |
| `POST /v1/conversations/search` | 搜索 L0 原始对话与工具事件。 |
| `POST /v1/offload/restore` | 按 `node_id` / `result_ref` 恢复被卸载的原始内容。 |

### 管理接口

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

---

## 🔧 可调参数

所有字段会尽量提供合理默认值。配置目标是：本地开发可以零配置启动，生产部署可以逐层展开。

<details>
<summary><b>🟢 Level 1 · 日常配置</b></summary>

| 字段 | 默认 | 说明 |
| :--- | :--- | :--- |
| `store.backend` | `sqlite` | 存储后端：`sqlite` / `postgres`。 |
| `recall.strategy` | `hybrid` | 召回策略：`keyword` / `vector` / `hybrid`。 |
| `recall.max_results` | `5` | 每次召回的记忆数量。 |
| `pipeline.enabled` | `true` | 是否启用异步 L1/L2/L3 演化。 |
| `offload.enabled` | `false` | 是否启用短期上下文卸载。 |

</details>

<details>
<summary><b>🟡 Level 2 · 长任务 / 长 Session 调优</b></summary>

| 字段 | 默认 | 说明 |
| :--- | :--- | :--- |
| `pipeline.every_n_turns` | `5` | 每 N 轮触发 L1 提取。 |
| `pipeline.idle_timeout_seconds` | `600` | 用户停止对话多久后触发记忆演化。 |
| `recall.timeout_ms` | `5000` | 召回超时时间；超时则跳过注入，避免阻塞主对话。 |
| `extraction.enable_dedup` | `true` | 是否启用 L1 去重与冲突检测。 |
| `offload.mild_ratio` | `0.5` | 温和压缩触发比例。 |
| `offload.aggressive_ratio` | `0.85` | 激进压缩触发比例。 |

</details>

<details>
<summary><b>🔴 Level 3 · 生产部署 / 自定义模型</b></summary>

| 字段 | 说明 |
| :--- | :--- |
| `embedding.*` | 远程 embedding 服务或本地 embedding 模型配置。 |
| `llm.*` | 独立 LLM 配置，用于 L1/L2/L3 提取、合并和画像生成。 |
| `postgres.*` | Postgres DSN、schema、连接池与迁移配置。 |
| `retention.*` | L0/L1/L2/L3 保留策略、归档策略和删除策略。 |
| `admin.*` | 管理 API 权限、指标和审计配置。 |

</details>

---

## 🤔 方案特点

### 1. 宏观画像 + 微观证据

日常对话中，Agent 可以优先使用 L3 Persona 和 L2 Scenario 快速理解用户偏好；当涉及事实、时间、项目细节时，再下钻到 L1 Atom 和 L0 Conversation。

| 问题类型 | 优先使用 | 必要时下钻 |
| :--- | :--- | :--- |
| 用户偏好、表达风格、长期目标 | L3 Persona / L2 Scenario | L1 Atom / L0 Conversation |
| 具体事实、日期、项目细节 | L1 Atom | L0 Conversation |
| 当前长任务恢复 | Mermaid task graph | summary.jsonl / refs 原文 |
| 历史任务复盘 | L2 Scenario / Metadata | node_id / result_ref |

### 2. 白盒可调试

OOM 计划把关键中间产物保存为可读结构，而不是只留下向量分数：

- L2 Scenario 可以是 Markdown。
- L3 Persona 可以是 Markdown 或结构化 JSON。
- 短期任务图可以是 Mermaid。
- 原文、摘要、节点之间通过 `event_id`、`source_event_ids`、`node_id`、`result_ref` 关联。

因此，记忆出错时可以逐层定位：

```text
Persona -> Scenario -> Atom -> Conversation -> raw tool result
```

### 3. 独立 Runtime，而不是某个 Agent 的插件

OOM 的默认接入方式是 REST / SDK。它可以服务多个 Agent，也可以在不同 Agent 框架之间共享同一套长期记忆。

```text
Agent A ─┐
Agent B ─┼─> Only-One-Memory Runtime ─> Store Adapter ─> Storage
Agent C ─┘
```

### 4. 异步演化，不阻塞主对话

捕获 L0 应该尽量快；L1/L2/L3 的提取、合并、画像更新、重建索引可以由异步 Pipeline 处理。主对话只负责及时写入事实，复杂演化放到后台 worker。

### 5. 保留来源与许可

本项目的架构和提示词设计参考并计划高保真复刻 TencentDB-Agent-Memory 的核心思想。复用或翻译其 prompt / design 时，应保留来源说明和 license notices。

---

## 📦 一期范围

V0.1 的目标不是只做 SQLite 本地 MVP，而是建立双后端基础能力：

- FastAPI skeleton
- `MemoryCore` lifecycle
- 配置系统
- SQLite schema + FTS5 + sqlite-vec
- Postgres schema + JSONB + tsvector / GIN + pgvector
- store backend selection
- `/v1/capture/turn`
- `/v1/conversations/search`
- `/v1/health`
- capture 幂等
- SQLite/Postgres migration smoke tests

---

## 🗺 路线图

| 版本 | 目标 | 状态 |
| :--- | :--- | :---: |
| **V0.1** | REST + MemoryCore + SQLite/Postgres L0 | Planned |
| **V0.2** | L1 Extraction + Hybrid Recall | Planned |
| **V0.3** | Pipeline 完整化 + Worker 化 | Planned |
| **V0.4** | L2 Scene + L3 Persona | Planned |
| **V0.5** | Context Offload + Mermaid 任务图 | Planned |
| **V0.6** | Production Hardening：权限、指标、审计、迁移、压测 | Planned |

首个可运行闭环是 **V0.1**；首个真正具备长期记忆能力的闭环是 **V0.2**；接近完整分层记忆和上下文卸载能力的版本是 **V0.5**。

---

## 📚 文档

| 文档 | 内容 |
| :--- | :--- |
| [`docs/superpowers/specs/2026-05-18-only-one-memory-design.md`](docs/superpowers/specs/2026-05-18-only-one-memory-design.md) | OOM 完整设计文档。 |
| [`docs/attribution/tencentdb-agent-memory.md`](docs/attribution/tencentdb-agent-memory.md) | TencentDB-Agent-Memory prompt 与设计归因说明。 |
| [`LICENSE`](LICENSE) | MIT License。 |

---

## 社区与贡献

Agent 记忆仍然是开放问题：什么该记、什么时候记、如何召回、如何修订、如何迁移，都值得一起探索。

欢迎提交：

- Bug 反馈
- 设计建议
- API 讨论
- 存储后端适配
- Benchmark 设计
- 文档勘误
- Pull Request

如果你对 Agent 长期记忆、上下文卸载、可追溯记忆或跨框架 Memory Runtime 感兴趣，欢迎参与 Only-One-Memory。

---

## 参考与许可

本项目的架构和提示词设计参考 [TencentDB-Agent-Memory](https://github.com/Tencent/TencentDB-Agent-Memory) 的核心思想。TencentDB-Agent-Memory 使用 MIT License；本项目复用或翻译其 prompt / design 时会保留来源说明和 license notices。

Only-One-Memory 本身使用 MIT License，详见 [LICENSE](LICENSE)。

---

<table>
  <tr>
    <td width="70%">
      <b>如果 Only-One-Memory 对你有帮助，欢迎为项目点亮 ⭐。</b><br />
      记忆不是为了让 AI 存下所有东西，而是为了让人不必重复所有事情。
    </td>
    <td width="30%" align="right">
      <b>OOM</b><br />
      REST-first · Python-native · Evidence-first
    </td>
  </tr>
</table>
