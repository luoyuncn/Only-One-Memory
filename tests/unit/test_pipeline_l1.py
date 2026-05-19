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


async def test_same_session_key_is_isolated_by_tenant():
    calls = []
    manager = PipelineManager(
        every_n_conversations=1,
        enable_warmup=False,
        l1_runner=lambda session_key, tenant_id: calls.append((tenant_id, session_key)),
    )

    await manager.notify_conversation("shared-session", tenant_id="tenant-a")
    await manager.notify_conversation("shared-session", tenant_id="tenant-b")

    assert calls == [("tenant-a", "shared-session"), ("tenant-b", "shared-session")]
    assert manager.state_for("shared-session", tenant_id="tenant-a") is not None
    assert manager.state_for("shared-session", tenant_id="tenant-b") is not None
    assert set(manager.dump_states_for_tenant("tenant-a")) == {"shared-session"}
