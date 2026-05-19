"""L3 persona 生成 prompt。"""

from __future__ import annotations

from oom.memory_core.prompts.attribution import PROMPT_LICENSE, TENCENTDB_AGENT_MEMORY_REPO


def build_persona_generation_prompt() -> str:
    return f"""你是 Only-One-Memory 的 L3 用户画像生成器。

参考设计：TencentDB-Agent-Memory ({TENCENTDB_AGENT_MEMORY_REPO})，License: {PROMPT_LICENSE}。

请根据 L2 场景摘要维护稳定、克制、可追溯的 persona.md。只能使用 persona 工具修改 persona.md。
不要把一次性任务误写成长期画像；优先保留偏好、交互协议、稳定工作方式。
"""
