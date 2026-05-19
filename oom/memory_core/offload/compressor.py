from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal


CompressionMode = Literal["mild", "aggressive"]


def compress_messages(
    messages: list[dict[str, Any]],
    entries: dict[str, dict[str, Any]],
    mode: CompressionMode = "mild",
    mermaid: str | None = None,
) -> list[dict[str, Any]]:
    compressed = [_compress_message(message, entries) for message in messages]
    if mode == "mild":
        return compressed
    if mode != "aggressive":
        raise ValueError("mode must be mild or aggressive")

    result = []
    if mermaid:
        result.append({"role": "system", "content": f"[Offload Mermaid Graph]\n{mermaid}"})
    for message in compressed:
        if message.get("role") == "tool" and message.get("tool_call_id") in entries:
            continue
        result.append(message)
    return result


def _compress_message(message: dict[str, Any], entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tool_call_id = message.get("tool_call_id")
    if message.get("role") != "tool" or tool_call_id not in entries:
        return deepcopy(message)

    entry = entries[tool_call_id]
    updated = deepcopy(message)
    updated["content"] = (
        "[Offloaded Tool Result]\n"
        f"node_id: {entry.get('node_id')}\n"
        f"result_ref: {entry.get('result_ref')}\n"
        f"summary: {entry.get('summary')}"
    )
    return updated
