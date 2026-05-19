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
