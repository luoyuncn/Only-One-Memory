from oom.memory_core.pipeline.manager import PipelineManager
from datetime import datetime, timedelta, timezone


async def test_flush_session_runs_only_named_session():
    calls = []
    manager = PipelineManager(every_n_conversations=5, enable_warmup=False, l1_runner=lambda key: calls.append(key))
    await manager.notify_conversation("s1")
    await manager.notify_conversation("s2")

    await manager.flush_session("s1")

    assert calls == ["s1"]


async def test_flush_idle_sessions_runs_inactive_session():
    calls = []
    manager = PipelineManager(
        every_n_conversations=5,
        enable_warmup=False,
        idle_timeout_seconds=60,
        l1_runner=lambda key: calls.append(key),
    )
    await manager.notify_conversation("s1")
    state = manager.state_for("s1")
    assert state is not None
    state.last_activity_at = datetime.now(timezone.utc) - timedelta(seconds=61)

    await manager.flush_idle_sessions()

    assert calls == ["s1"]
