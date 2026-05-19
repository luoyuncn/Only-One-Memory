from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from oom.memory_core.offload.types import OffloadEntry


def build_offload_entry(
    *,
    session_id: str,
    tool_call_id: str,
    tool_name: str,
    summary: str,
    score: int,
    result_ref: str,
    tenant_id: str = "default",
    node_id: str | None = None,
) -> OffloadEntry:
    final_node_id = node_id or f"N{abs(hash((session_id, tool_call_id))) % 100000}"
    entry_id = str(uuid5(NAMESPACE_URL, f"{tenant_id}:{session_id}:{tool_call_id}:{result_ref}"))
    return OffloadEntry(
        id=entry_id,
        tenant_id=tenant_id,
        session_id=session_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        summary=summary,
        score=score,
        node_id=final_node_id,
        result_ref=result_ref,
        created_at=datetime.now(timezone.utc),
    )
