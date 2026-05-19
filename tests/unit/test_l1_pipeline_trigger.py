from oom.memory_core.pipeline.manager import PipelineManager


async def test_l1_threshold_triggers_on_first_warmup_turn():
    calls = []
    manager = PipelineManager(
        every_n_conversations=5,
        enable_warmup=True,
        l1_runner=lambda session_key: calls.append(session_key),
    )

    await manager.notify_conversation("agent:u1:s1")

    assert calls == ["agent:u1:s1"]
