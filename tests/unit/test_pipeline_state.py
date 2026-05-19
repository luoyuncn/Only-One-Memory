from oom.memory_core.pipeline.checkpoint import PipelineSessionState


def test_new_session_state_starts_with_warmup_threshold_one():
    state = PipelineSessionState.new(session_key="agent:u1:s1", enable_warmup=True)

    assert state.session_key == "agent:u1:s1"
    assert state.conversation_count == 0
    assert state.warmup_threshold == 1
    assert state.last_activity_at is not None
