from oom.memory_core.scene.scene_extractor import SceneExtractor


class FakeSceneLlm:
    async def run_with_tools(self, system_prompt, user_prompt, tools):
        await tools.write_scene(
            "agent-memory.md",
            "-----META-START-----\n"
            "created: 2026-05-19T00:00:00Z\n"
            "updated: 2026-05-19T00:00:00Z\n"
            "summary: 用户构建 Agent 记忆系统。\n"
            "heat: 1\n"
            "-----META-END-----\n\n"
            "## 用户核心特征\n用户重视证据链。",
        )
        return "done"


async def test_scene_extractor_writes_scene(tmp_path):
    extractor = SceneExtractor(data_dir=tmp_path, llm_runner=FakeSceneLlm(), max_scenes=15)

    result = await extractor.extract(memories=[{"id": "mem1", "content": "用户重视证据链"}])

    assert result.scenes_created == 1


class FakeSceneStore:
    def __init__(self):
        self.scenes = []

    async def upsert_scene(self, scene):
        self.scenes.append(scene)
        return scene


async def test_scene_extractor_syncs_scenes_to_store(tmp_path):
    store = FakeSceneStore()
    extractor = SceneExtractor(data_dir=tmp_path, llm_runner=FakeSceneLlm(), max_scenes=15, store=store)

    await extractor.extract(
        memories=[
            {
                "id": "mem1",
                "tenant_id": "default",
                "user_id": "u1",
                "content": "用户重视证据链",
            }
        ]
    )

    assert store.scenes[0].tenant_id == "default"
    assert store.scenes[0].user_id == "u1"
    assert store.scenes[0].summary == "用户构建 Agent 记忆系统。"
