"""把检索命中组装为可注入 Agent 上下文的文本块。"""

from __future__ import annotations

from oom.memory_core.types import ConversationSearchHit, MemorySearchHit


def build_dynamic_context(memory_hits: list[MemorySearchHit], conversation_hits: list[ConversationSearchHit]) -> str:
    lines: list[str] = []
    if memory_hits:
        lines.append("## 相关长期记忆")
        lines.extend(f"- {hit.memory.content}" for hit in memory_hits)
    if conversation_hits:
        lines.append("## 相关原始对话")
        lines.extend(f"- {hit.event.role}: {hit.event.content}" for hit in conversation_hits)
    return "\n".join(lines)
