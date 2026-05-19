from oom.memory_core.llm.json_utils import parse_json_array


def test_parse_json_array_from_markdown_fence():
    raw = '```json\n[{"scene_name":"s","message_ids":["m1"],"memories":[]}]\n```'

    parsed = parse_json_array(raw)

    assert parsed == [{"scene_name": "s", "message_ids": ["m1"], "memories": []}]


def test_parse_json_array_with_prefix_and_suffix():
    raw = '结果如下：[{"record_id":"r1","action":"store"}] 完成'

    parsed = parse_json_array(raw)

    assert parsed[0]["record_id"] == "r1"
