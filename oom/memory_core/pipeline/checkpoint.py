from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class PipelineSessionState(BaseModel):
    session_key: str
    tenant_id: str = "default"
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
    def new(cls, session_key: str, enable_warmup: bool, tenant_id: str = "default") -> PipelineSessionState:
        return cls(
            session_key=session_key,
            tenant_id=tenant_id,
            warmup_threshold=1 if enable_warmup else 0,
            last_activity_at=datetime.now(timezone.utc),
        )


class CheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def load(self) -> dict[str, PipelineSessionState]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {key: PipelineSessionState.model_validate(value) for key, value in raw.items()}

    async def save(self, states: dict[str, PipelineSessionState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        payload = {key: state.model_dump(mode="json") for key, state in states.items()}
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)
