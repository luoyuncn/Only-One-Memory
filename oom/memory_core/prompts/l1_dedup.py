"""L1 去重 prompt。"""

from __future__ import annotations

from oom.memory_core.prompts.attribution import PROMPT_LICENSE, TENCENTDB_AGENT_MEMORY_REPO


def build_l1_dedup_prompt() -> str:
    return f"""你是 Only-One-Memory 的 L1 记忆去重与冲突检测器。

参考设计：TencentDB-Agent-Memory ({TENCENTDB_AGENT_MEMORY_REPO})，License: {PROMPT_LICENSE}。

请比较候选记忆与已有记忆，判断每条候选应 store、merge、ignore 或 conflict。只输出 JSON 数组，
每项包含 record_id、action、target_id、reason。
"""
