"""MemoryCore 对外 API 和内部层级数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MessageRole = Literal["system", "user", "assistant", "tool"]
MemoryType = Literal["persona", "episodic", "instruction"]


class ConversationMessage(BaseModel):
    """一次 turn 中的单条消息，进入 L0 前保持原始角色和时间。"""

    role: MessageRole
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolEvent(BaseModel):
    """工具调用事件的通用表示，后续可接入 offload 或审计链路。"""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | str | None = None
    timestamp: datetime | None = None


class CaptureTurnRequest(BaseModel):
    """采集一次对话 turn 的请求体。"""

    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    session_key: str
    idempotency_key: str = Field(min_length=1)
    messages: list[ConversationMessage] = Field(min_length=1)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaptureResult(BaseModel):
    """采集完成后的 L0 写入结果。"""

    l0_recorded_count: int
    event_ids: list[str]
    idempotency_key: str


class ConversationSearchRequest(BaseModel):
    """L0 原始对话搜索请求。"""

    tenant_id: str
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    session_key: str | None = None
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class L0Event(BaseModel):
    """L0 原始事件，是所有上层记忆的证据源。"""

    id: str
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    session_key: str
    role: MessageRole
    content: str
    event_ts: datetime
    recorded_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationSearchHit(BaseModel):
    """L0 搜索命中，score 由具体 store 的检索实现给出。"""

    event: L0Event
    score: float


class ConversationSearchResult(BaseModel):
    """L0 搜索响应。"""

    total: int
    hits: list[ConversationSearchHit]


class MemoryAtom(BaseModel):
    """L1 原子记忆。

    它是可检索、可去重、可追溯的最小长期记忆单元，必须保留 source_event_ids。
    """

    id: str
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    session_key: str
    content: str
    type: MemoryType
    priority: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    scene_name: str | None = None
    source_event_ids: list[str] = Field(default_factory=list)
    timestamps: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class MemorySearchHit(BaseModel):
    """L1 搜索命中。"""

    memory: MemoryAtom
    score: float


class MemorySearchRequest(BaseModel):
    """L1 原子记忆搜索请求。"""

    tenant_id: str
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    session_key: str | None = None
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class MemorySearchResult(BaseModel):
    """L1 搜索响应。"""

    total: int
    hits: list[MemorySearchHit]


class RecallBeforeRequest(BaseModel):
    """Agent 回复前召回请求。"""

    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    session_key: str
    user_text: str
    max_results: int = Field(default=5, ge=1, le=20)


class RecallBeforeResult(BaseModel):
    """召回结果，dynamic_context 可直接注入 Agent 上下文。"""

    stable_context: str = ""
    dynamic_context: str
    memory_hits: list[MemorySearchHit] = Field(default_factory=list)
    conversation_hits: list[ConversationSearchHit] = Field(default_factory=list)


class SceneBlock(BaseModel):
    """L2 场景 Markdown 块，把多个 L1 事实组织成可读主题。"""

    id: str
    tenant_id: str
    user_id: str
    filename: str
    content: str
    summary: str = ""
    heat: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


class SceneListResult(BaseModel):
    """场景列表响应。"""

    items: list[SceneBlock] = Field(default_factory=list)


class ScenePatchRequest(BaseModel):
    """手动更新或创建场景的请求体。"""

    tenant_id: str
    user_id: str
    content: str
    summary: str = ""
    heat: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfileDocument(BaseModel):
    """L3 画像/profile 文档，描述稳定偏好、交互协议或长期特征。"""

    scope: str
    scope_id: str
    tenant_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


class ProfilePatchRequest(BaseModel):
    """手动更新画像文档的请求体。"""

    tenant_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoreCapabilities(BaseModel):
    """Store 能力声明，MemoryCore 依赖它决定是否启用向量召回等高级路径。"""

    fts_search: bool
    vector_search: bool
    backend: str
    vector_backend: str | None = None
