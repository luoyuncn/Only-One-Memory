from datetime import datetime, timezone

from oom.memory_core.types import CaptureTurnRequest, ConversationMessage


def test_capture_request_requires_idempotency_key():
    request = CaptureTurnRequest(
        tenant_id="default",
        user_id="u1",
        agent_id="a1",
        session_id="s1",
        session_key="agent:u1:s1",
        idempotency_key="turn-1",
        messages=[
            ConversationMessage(
                role="user",
                content="hello",
                timestamp=datetime(2026, 5, 19, tzinfo=timezone.utc),
            )
        ],
    )

    assert request.messages[0].role == "user"
    assert request.session_key == "agent:u1:s1"
