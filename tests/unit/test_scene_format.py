import pytest

from oom.memory_core.scene.scene_format import format_scene_block, parse_scene_block
from oom.memory_core.scene.scene_index import build_scene_index


def test_scene_block_round_trip():
    markdown = format_scene_block(
        created="2026-05-19T00:00:00Z",
        updated="2026-05-19T00:00:00Z",
        summary="用户在构建 Agent 记忆系统。",
        heat=3,
        body="## 用户核心特征\n用户重视可追溯记忆。",
    )

    parsed = parse_scene_block(markdown, filename="agent-memory.md")

    assert parsed.filename == "agent-memory.md"
    assert parsed.meta.created == "2026-05-19T00:00:00Z"
    assert parsed.meta.updated == "2026-05-19T00:00:00Z"
    assert parsed.meta.summary == "用户在构建 Agent 记忆系统。"
    assert parsed.meta.heat == 3
    assert "可追溯" in parsed.body


def test_parse_scene_block_requires_strict_meta_markers():
    with pytest.raises(ValueError, match="META"):
        parse_scene_block("created: now\n\nbody", filename="broken.md")


def test_parse_scene_block_requires_all_meta_fields():
    markdown = """-----META-START-----
created: 2026-05-19T00:00:00Z
updated: 2026-05-19T00:00:00Z
summary: 缺少热度。
-----META-END-----

body
"""

    with pytest.raises(ValueError, match="heat"):
        parse_scene_block(markdown, filename="missing-heat.md")


def test_build_scene_index_sorts_items_by_filename():
    beta = format_scene_block(
        created="2026-05-19T00:00:00Z",
        updated="2026-05-19T00:00:00Z",
        summary="第二个场景。",
        heat=2,
        body="beta",
    )
    alpha = format_scene_block(
        created="2026-05-18T00:00:00Z",
        updated="2026-05-18T00:00:00Z",
        summary="第一个场景。",
        heat=1,
        body="alpha",
    )

    items = build_scene_index({"beta.md": beta, "alpha.md": alpha})

    assert [item.filename for item in items] == ["alpha.md", "beta.md"]
    assert items[0].summary == "第一个场景。"
    assert items[1].heat == 2
