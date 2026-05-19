from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from oom.memory_core.types import MemoryAtom


DedupAction = Literal["store", "merge", "ignore", "conflict"]


@dataclass(frozen=True)
class DedupDecision:
    memory_id: str
    action: DedupAction
    target_id: str | None = None
    reason: str = ""


def dedup_by_exact_content(candidates: list[MemoryAtom], existing: list[MemoryAtom]) -> list[DedupDecision]:
    existing_by_content = {memory.content: memory.id for memory in existing}
    decisions = []
    for candidate in candidates:
        target_id = existing_by_content.get(candidate.content)
        if target_id is None:
            decisions.append(DedupDecision(memory_id=candidate.id, action="store", reason="new content"))
        else:
            decisions.append(DedupDecision(memory_id=candidate.id, action="ignore", target_id=target_id, reason="duplicate"))
    return decisions
