from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from oom.memory_core.offload.types import OffloadRef


class OffloadRefStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def create_ref(
        self,
        *,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        session_id: str,
        kind: str,
        content: str,
        metadata: dict | None = None,
    ) -> OffloadRef:
        ref = OffloadRef(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            kind=kind,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
            content=content,
        )
        path = self._path_for(ref.id)
        path.write_text(json.dumps(ref.model_dump(mode="json"), ensure_ascii=False), encoding="utf-8")
        return ref

    def get_ref(self, ref_id: str) -> OffloadRef | None:
        path = self._path_for(ref_id)
        if not path.exists():
            return None
        return OffloadRef.model_validate_json(path.read_text(encoding="utf-8"))

    def _path_for(self, ref_id: str) -> Path:
        self._validate_ref_id(ref_id)
        path = (self.data_dir / f"{ref_id}.json").resolve()
        data_dir = self.data_dir.resolve()
        if path.parent != data_dir:
            raise ValueError("ref_id must not escape data_dir")
        return path

    @staticmethod
    def _validate_ref_id(ref_id: str) -> None:
        if not ref_id or ref_id in {".", ".."} or "/" in ref_id or "\\" in ref_id:
            raise ValueError("ref_id must be a single file-safe identifier")
