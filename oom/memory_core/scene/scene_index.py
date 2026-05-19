from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from oom.memory_core.scene.scene_format import parse_scene_block


@dataclass(frozen=True)
class SceneIndexItem:
    filename: str
    created: str
    updated: str
    summary: str
    heat: int


def build_scene_index(scene_markdown_by_filename: Mapping[str, str]) -> list[SceneIndexItem]:
    items = [
        _build_item(filename=filename, markdown=markdown)
        for filename, markdown in scene_markdown_by_filename.items()
    ]
    return sorted(items, key=lambda item: item.filename)


def _build_item(filename: str, markdown: str) -> SceneIndexItem:
    parsed = parse_scene_block(markdown, filename=filename)
    return SceneIndexItem(
        filename=parsed.filename,
        created=parsed.meta.created,
        updated=parsed.meta.updated,
        summary=parsed.meta.summary,
        heat=parsed.meta.heat,
    )

