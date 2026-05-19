from oom.memory_core.offload.compressor import compress_messages


def test_compress_messages_replaces_old_tool_result_with_summary():
    messages = [
        {"role": "tool", "tool_call_id": "call1", "content": "long raw"},
        {"role": "user", "content": "continue"},
    ]
    entries = {"call1": {"summary": "short summary", "node_id": "N1", "result_ref": "ref1"}}

    compressed = compress_messages(messages, entries, mode="mild")

    assert compressed[0]["content"].startswith("[Offloaded Tool Result")
    assert "ref1" in compressed[0]["content"]
