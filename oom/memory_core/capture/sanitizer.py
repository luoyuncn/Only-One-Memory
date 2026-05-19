from __future__ import annotations

from only_one_memory.memory_core.types import ConversationMessage


def sanitize_messages(messages: list[ConversationMessage]) -> list[ConversationMessage]:
    sanitized = []
    for message in messages:
        content = " ".join(message.content.split())
        if not content:
            continue
        sanitized.append(message.model_copy(update={"content": content}))
    return sanitized
