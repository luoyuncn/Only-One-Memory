from oom.memory_core.offload.mermaid_builder import build_mermaid_graph
from oom.memory_core.offload.types import OffloadEntry


def test_mermaid_graph_contains_node_and_result_ref():
    graph = build_mermaid_graph(
        [
            OffloadEntry(
                id="e1",
                session_id="s1",
                tool_call_id="call1",
                tool_name="read_file",
                summary="读取 README",
                score=8,
                node_id="N1",
                result_ref="ref1",
            )
        ]
    )

    assert "flowchart TD" in graph
    assert "N1" in graph
    assert "ref1" in graph
