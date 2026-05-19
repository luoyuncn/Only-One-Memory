from __future__ import annotations

from oom.memory_core.prompts.attribution import PROMPT_LICENSE, TENCENTDB_AGENT_MEMORY_REPO


def build_l1_extraction_prompt() -> str:
    return f"""你是 Only-One-Memory 的 L1 原子记忆抽取器。

参考设计：TencentDB-Agent-Memory ({TENCENTDB_AGENT_MEMORY_REPO})，License: {PROMPT_LICENSE}。

请从新增消息中提取长期有价值、可追溯的原子记忆。只输出 JSON 数组，每个场景对象包含：
- scene_name: 场景名
- message_ids: 证据消息 ID 列表
- memories: 原子记忆列表

每条 memory 包含 content、type、priority、source_message_ids、metadata。不要输出解释文本。
"""
