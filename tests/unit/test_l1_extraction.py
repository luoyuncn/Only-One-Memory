from oom.memory_core.extraction.l1_extractor import L1Extractor


class FakeLlmRunner:
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        return '[{"scene_name":"我在和用户做Agent记忆系统","message_ids":["evt1"],"memories":[{"content":"用户正在开发 Only-One-Memory。","type":"episodic","priority":90,"source_message_ids":["evt1"],"metadata":{}}]}]'


async def test_l1_extractor_parses_scene_segment():
    extractor = L1Extractor(llm_runner=FakeLlmRunner())

    result = await extractor.extract(
        new_messages=[
            {
                "id": "evt1",
                "role": "user",
                "content": "我在开发 Only-One-Memory",
                "timestamp": "2026-05-19T00:00:00Z",
            }
        ]
    )

    assert result.scene_names == ["我在和用户做Agent记忆系统"]
    assert result.memories[0].content == "用户正在开发 Only-One-Memory。"
