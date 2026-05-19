from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from oom.memory_core.persona.tool_runner import PersonaToolRunner
from oom.memory_core.prompts.persona_generation import build_persona_generation_prompt
from oom.memory_core.scene.scene_navigation import build_scene_navigation, strip_scene_navigation


class PersonaLlmRunner(Protocol):
    async def run_with_tools(self, system_prompt: str, user_prompt: str, tools: PersonaToolRunner) -> str: ...


@dataclass(frozen=True)
class PersonaGenerationResult:
    updated: bool
    path: str


class PersonaGenerator:
    def __init__(self, data_dir: str | Path, llm_runner: PersonaLlmRunner) -> None:
        self.data_dir = Path(data_dir)
        self.llm_runner = llm_runner

    async def generate(self, scenes: list[dict[str, Any]]) -> PersonaGenerationResult:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tools = PersonaToolRunner(self.data_dir)
        before = tools.read_persona()
        await self.llm_runner.run_with_tools(
            build_persona_generation_prompt(),
            json.dumps({"current_persona": before, "scenes": scenes}, ensure_ascii=False),
            tools,
        )
        generated = strip_scene_navigation(tools.read_persona())
        after = f"{generated}\n\n{build_scene_navigation(scenes)}\n"
        await tools.write_persona(after)
        return PersonaGenerationResult(updated=after != before, path=str(self.data_dir / "persona.md"))
