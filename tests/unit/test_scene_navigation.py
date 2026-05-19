from oom.memory_core.scene.scene_navigation import build_scene_navigation


def test_scene_navigation_lists_scene_refs_stably():
    navigation = build_scene_navigation(
        [
            {"filename": "beta.md", "summary": "第二个场景"},
            {"filename": "alpha.md", "summary": "第一个场景"},
        ]
    )

    assert "## 场景导航" in navigation
    assert navigation.index("alpha.md") < navigation.index("beta.md")
