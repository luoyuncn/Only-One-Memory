from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MessageRole = Literal["system", "user", "assistant", "tool"]


class ConversationMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolEvent(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | str | None = None
    timestamp: datetime | None = None


class CaptureTurnRequest(BaseModel):
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
    l0_recorded_count: int
    event_ids: list[str]
    idempotency_key: str


class ConversationSearchRequest(BaseModel):
    tenant_id: str
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    session_key: str | None = None
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class L0Event(BaseModel):
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
    event: L0Event
    score: float


class ConversationSearchResult(BaseModel):
    total: int
    hits: list[ConversationSearchHit]


class StoreCapabilities(BaseModel):
    fts_search: bool
    vector_search: bool
    backend: str
    vector_backend: str | None = None
