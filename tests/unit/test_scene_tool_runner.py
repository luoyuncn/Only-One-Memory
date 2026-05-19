import pytest

from oom.memory_core.scene.tool_runner import SceneToolRunner


async def test_scene_runner_rejects_path_traversal(tmp_path):
    runner = SceneToolRunner(root=tmp_path, readable_files={"safe.md"})

    with pytest.raises(ValueError, match="path traversal"):
        await runner.read_scene("../secret.md")


async def test_scene_runner_allows_whitelisted_read(tmp_path):
    (tmp_path / "safe.md").write_text("hello", encoding="utf-8")
    runner = SceneToolRunner(root=tmp_path, readable_files={"safe.md"})

    assert await runner.read_scene("safe.md") == "hello"
