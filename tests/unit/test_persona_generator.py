import pytest

from oom.memory_core.persona.persona_generator import PersonaGenerator
from oom.memory_core.persona.tool_runner import PersonaToolRunner


async def test_persona_runner_only_allows_persona_file(tmp_path):
    runner = PersonaToolRunner(root=tmp_path)

    with pytest.raises(ValueError, match="persona.md"):
        await runner.write_file("other.md", "bad")


class FakePersonaLlm:
    async def run_with_tools(self, system_prompt, user_prompt, tools):
        await tools.write_persona("# 用户画像\n用户重视证据链。")
        return "done"


async def test_persona_generator_writes_persona(tmp_path):
    generator = PersonaGenerator(data_dir=tmp_path, llm_runner=FakePersonaLlm())

    result = await generator.generate(scenes=[{"filename": "agent-memory.md", "summary": "用户重视证据链"}])

    assert result.updated is True
    assert "证据链" in (tmp_path / "persona.md").read_text(encoding="utf-8")


async def test_persona_generator_appends_scene_navigation(tmp_path):
    generator = PersonaGenerator(data_dir=tmp_path, llm_runner=FakePersonaLlm())

    await generator.generate(scenes=[{"filename": "agent-memory.md", "summary": "用户重视证据链"}])

    content = (tmp_path / "persona.md").read_text(encoding="utf-8")
    assert "## 场景导航" in content
    assert "agent-memory.md" in content
