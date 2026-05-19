"""审计日志模型与写入服务，记录管理侧高风险操作。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class AuditStore(Protocol):
    async def write_audit_event(self, event: "AuditEvent") -> "AuditEvent": ...

    async def list_audit_events(self, tenant_id: str | None = None) -> list["AuditEvent"]: ...


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    actor: str
    action: str
    target: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogger:
    def __init__(self, store: AuditStore | None = None) -> None:
        self._store = store
        self._events: list[AuditEvent] = []

    @property
    def events(self) -> list[AuditEvent]:
        return list(self._events)

    def write(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    async def awrite(self, event: AuditEvent) -> AuditEvent:
        self.write(event)
        if self._store is not None:
            return await self._store.write_audit_event(event)
        return event
