"""Persona 生成触发策略。"""

from __future__ import annotations


def should_generate_persona(changed_scene_count: int, threshold: int = 1) -> bool:
    return changed_scene_count >= threshold
