from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, Field

from oom.memory_core.llm.json_utils import parse_json_array
from oom.memory_core.prompts.l1_extraction import build_l1_extraction_prompt
from oom.memory_core.types import MemoryAtom, MemoryType


class LlmRunner(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> str: ...


class CandidateMemory(BaseModel):
    content: str
    type: MemoryType = "episodic"
    priority: int = Field(default=50, ge=0, le=100)
    source_message_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class L1ExtractionResult:
    scene_names: list[str]
    memories: list[MemoryAtom]


class L1Extractor:
    def __init__(self, llm_runner: LlmRunner, tenant_id: str = "default") -> None:
        self.llm_runner = llm_runner
        self.tenant_id = tenant_id

    async def extract(self, new_messages: list[dict[str, Any]]) -> L1ExtractionResult:
        system_prompt = build_l1_extraction_prompt()
        raw = await self.llm_runner.complete(system_prompt=system_prompt, user_prompt=json.dumps(new_messages, ensure_ascii=False))
        scenes = parse_json_array(raw)

        now = datetime.now(timezone.utc)
        messages_by_id = {str(message.get("id")): message for message in new_messages if message.get("id") is not None}
        scene_names: list[str] = []
        memories: list[MemoryAtom] = []
        for scene in scenes:
            scene_name = str(scene.get("scene_name") or "")
            if scene_name:
                scene_names.append(scene_name)
            for item in scene.get("memories", []):
                candidate = CandidateMemory.model_validate(item)
                source_ids = candidate.source_message_ids or list(scene.get("message_ids", []))
                first_message = messages_by_id.get(source_ids[0]) if source_ids else None
                timestamps = self._timestamps_for(source_ids, messages_by_id)
                memories.append(
                    MemoryAtom(
                        id=self._memory_id(candidate.content, source_ids),
                        tenant_id=self.tenant_id,
                        user_id=str(first_message.get("user_id", "")) if first_message else "",
                        agent_id=str(first_message.get("agent_id", "")) if first_message else "",
                        session_id=str(first_message.get("session_id", "")) if first_message else "",
                        session_key=str(first_message.get("session_key", "")) if first_message else "",
                        content=candidate.content,
                        type=candidate.type,
                        priority=candidate.priority,
                        confidence=0.8,
                        scene_name=scene_name or None,
                        source_event_ids=source_ids,
                        timestamps=timestamps,
                        metadata=candidate.metadata,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return L1ExtractionResult(scene_names=scene_names, memories=memories)

    @staticmethod
    def _timestamps_for(source_ids: list[str], messages_by_id: dict[str, dict[str, Any]]) -> list[str]:
        timestamps = []
        for source_id in source_ids:
            timestamp = messages_by_id.get(source_id, {}).get("timestamp")
            if timestamp is not None:
                timestamps.append(str(timestamp))
        return timestamps

    @staticmethod
    def _memory_id(content: str, source_ids: list[str]) -> str:
        raw = f"{content}:{','.join(source_ids)}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))
