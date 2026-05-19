from oom.memory_core.pipeline.manager import PipelineManager


async def test_l3_pending_reruns_after_current_run():
    calls = []

    async def l3_runner():
        calls.append("l3")

    manager = PipelineManager(every_n_conversations=1, enable_warmup=False, l3_runner=l3_runner)
    manager.mark_l3_running_for_test(True)
    manager.trigger_l3()
    manager.mark_l3_running_for_test(False)
    await manager.drain_l3_for_test()

    assert calls == ["l3"]
