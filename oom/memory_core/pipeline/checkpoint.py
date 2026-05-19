from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PipelineSessionState(BaseModel):
    session_key: str
    conversation_count: int = Field(default=0, ge=0)
    warmup_threshold: int = Field(default=0, ge=0)
    last_l1_cursor: str | None = None
    last_scene_name: str | None = None
    l2_cursor: str | None = None
    l2_pending_l1_count: int = Field(default=0, ge=0)
    last_l2_at: datetime | None = None
    last_activity_at: datetime
    l1_retry_count: int = Field(default=0, ge=0)

    @classmethod
    def new(cls, session_key: str, enable_warmup: bool) -> PipelineSessionState:
        return cls(
            session_key=session_key,
            warmup_threshold=1 if enable_warmup else 0,
            last_activity_at=datetime.now(timezone.utc),
        )
