from __future__ import annotations

import re

from oom.memory_core.offload.types import OffloadEntry


def build_mermaid_graph(entries: list[OffloadEntry]) -> str:
    lines = ["flowchart TD"]
    sorted_entries = sorted(entries, key=lambda entry: (entry.created_at.isoformat() if entry.created_at else "", entry.node_id))
    previous_node = None
    for entry in sorted_entries:
        label = _escape_label(f"{entry.tool_name}: {entry.summary}\\nref={entry.result_ref}")
        lines.append(f'    {entry.node_id}["{label}"]')
        if previous_node is not None:
            lines.append(f"    {previous_node} --> {entry.node_id}")
        previous_node = entry.node_id
    return "\n".join(lines)


def _escape_label(value: str) -> str:
    return re.sub(r'["<>]', "", value)
