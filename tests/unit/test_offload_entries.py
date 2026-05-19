from oom.memory_core.offload.state_manager import build_offload_entry


def test_build_offload_entry_links_result_ref():
    entry = build_offload_entry(
        session_id="s1",
        tool_call_id="call1",
        tool_name="read_file",
        summary="读取设计文档",
        score=8,
        result_ref="ref1",
    )

    assert entry.tool_call_id == "call1"
    assert entry.result_ref == "ref1"
