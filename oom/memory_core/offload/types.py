"""Context Offload 的 Pydantic 数据结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OffloadRef(BaseModel):
    """被卸载原文的完整文件记录。"""

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
    """创建 offload ref 的 API 请求。"""

    tenant_id: str
    user_id: str
    agent_id: str
    session_id: str
    kind: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RestoreOffloadRequest(BaseModel):
    """恢复 offload 原文的请求，可用 result_ref 或 node_id 定位。"""

    tenant_id: str
    session_id: str
    result_ref: str | None = None
    node_id: str | None = None


class RestoreOffloadResult(BaseModel):
    """恢复出的原文及引用信息。"""

    raw_content: str
    result_ref: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OffloadEntry(BaseModel):
    """上下文中保留的轻量工具结果条目。"""

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
    """创建 offload entry 的 API 请求。"""

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
