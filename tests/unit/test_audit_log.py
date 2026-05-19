from datetime import datetime, timezone

from oom.memory_core.admin.audit import AuditEvent, AuditLogger


def test_audit_event_contains_actor_and_action():
    event = AuditEvent(
        actor="admin:u1",
        action="memory.review",
        target="memory:l1:fact-1",
        created_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )

    assert event.actor == "admin:u1"
    assert event.action == "memory.review"


def test_audit_logger_write_keeps_events_in_memory():
    logger = AuditLogger()
    event = AuditEvent(
        actor="admin:u1",
        action="memory.review",
        target="memory:l1:fact-1",
        metadata={"reason": "manual-check"},
        created_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )

    written = logger.write(event)

    assert written == event
    assert logger.events == [event]
