from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid5, NAMESPACE_URL

from oom.memory_core.observability.metrics import increment
from oom.memory_core.prompts.scene_extraction import build_scene_extraction_prompt
from oom.memory_core.scene.scene_format import parse_scene_block
from oom.memory_core.scene.scene_index import build_scene_index
from oom.memory_core.scene.tool_runner import SceneToolRunner
from oom.memory_core.types import SceneBlock


class SceneLlmRunner(Protocol):
    async def run_with_tools(self, system_prompt: str, user_prompt: str, tools: SceneToolRunner) -> str: ...


@dataclass(frozen=True)
class SceneExtractionResult:
    scenes_created: int
    scenes_updated: int
    scene_files: list[str]


class SceneExtractor:
    def __init__(
        self,
        data_dir: str | Path,
        llm_runner: SceneLlmRunner,
        max_scenes: int = 15,
        store: Any | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.llm_runner = llm_runner
        self.max_scenes = max_scenes
        self.store = store

    async def extract(self, memories: list[dict[str, Any]]) -> SceneExtractionResult:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        before = self._scene_files()
        runner = SceneToolRunner(root=self.data_dir, readable_files=set(before))
        prompt = build_scene_extraction_prompt()
        user_prompt = json.dumps(
            {
                "max_scenes": self.max_scenes,
                "scene_index": [item.__dict__ for item in build_scene_index(self._scene_markdown())],
                "memories": memories,
            },
            ensure_ascii=False,
        )
        await self.llm_runner.run_with_tools(prompt, user_prompt, runner)
        self._remove_deleted_files()
        after = self._scene_files()
        self._validate_scenes(after)
        await self._sync_store(after, memories)
        increment("oom_l2_scene_generation_total")
        return SceneExtractionResult(
            scenes_created=len(set(after) - set(before)),
            scenes_updated=len(set(after) & set(before)),
            scene_files=after,
        )

    def _scene_files(self) -> list[str]:
        return sorted(path.name for path in self.data_dir.glob("*.md") if path.is_file())

    def _scene_markdown(self) -> dict[str, str]:
        return {filename: (self.data_dir / filename).read_text(encoding="utf-8") for filename in self._scene_files()}

    def _remove_deleted_files(self) -> None:
        for path in self.data_dir.glob("*.md"):
            if path.read_text(encoding="utf-8") == "[DELETED]":
                path.unlink()

    def _validate_scenes(self, filenames: list[str]) -> None:
        for filename in filenames:
            parse_scene_block((self.data_dir / filename).read_text(encoding="utf-8"), filename=filename)

    async def _sync_store(self, filenames: list[str], memories: list[dict[str, Any]]) -> None:
        if self.store is None:
            return
        tenant_id = str(memories[0].get("tenant_id", "default")) if memories else "default"
        user_id = str(memories[0].get("user_id", "")) if memories else ""
        for filename in filenames:
            content = (self.data_dir / filename).read_text(encoding="utf-8")
            parsed = parse_scene_block(content, filename=filename)
            scene_id = str(uuid5(NAMESPACE_URL, f"{tenant_id}:{user_id}:{filename}"))
            await self.store.upsert_scene(
                SceneBlock(
                    id=scene_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    filename=filename,
                    content=content,
                    summary=parsed.meta.summary,
                    heat=parsed.meta.heat,
                    metadata={"source": "scene_extractor"},
                    updated_at=parsed.meta.updated,
                )
            )
