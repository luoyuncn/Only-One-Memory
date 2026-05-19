from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OffloadRef(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    kind: str
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    content: str


class CreateOffloadRefRequest(BaseModel):
    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    kind: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestoreOffloadRequest(BaseModel):
    tenant_id: str
    session_id: str
    result_ref: str | None = None
    node_id: str | None = None


class RestoreOffloadResult(BaseModel):
    raw_content: str
    result_ref: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OffloadEntry(BaseModel):
    id: str
    tenant_id: str = "default"
    user_id: str = ""
    agent_id: str = ""
    session_id: str
    tool_call_id: str
    tool_name: str
    summary: str
    score: int
    node_id: str
    result_ref: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class CreateOffloadEntryRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str = ""
    agent_id: str = ""
    session_id: str
    tool_call_id: str
    tool_name: str
    summary: str
    score: int
    node_id: str | None = None
    result_ref: str
    metadata: dict[str, Any] = Field(default_factory=dict)
