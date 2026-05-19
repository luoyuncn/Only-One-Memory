from __future__ import annotations

from typing import Any


NAVIGATION_TITLE = "## 场景导航"


def build_scene_navigation(scenes: list[dict[str, Any]]) -> str:
    lines = [NAVIGATION_TITLE]
    for scene in sorted(scenes, key=lambda item: str(item.get("filename", ""))):
        filename = str(scene.get("filename", ""))
        summary = str(scene.get("summary", ""))
        lines.append(f"- `{filename}`：{summary}")
    return "\n".join(lines).rstrip()


def strip_scene_navigation(content: str) -> str:
    index = content.find(NAVIGATION_TITLE)
    if index < 0:
        return content.rstrip()
    return content[:index].rstrip()
