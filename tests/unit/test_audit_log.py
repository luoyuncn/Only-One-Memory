from datetime import datetime, timezone

from oom.memory_core.admin.audit import AuditEvent, AuditLogger
from oom.memory_core.config import SqliteConfig
from oom.memory_core.stores.sqlite_store import SqliteMemoryStore


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


async def test_audit_logger_persists_to_sqlite_store(tmp_path):
    store = SqliteMemoryStore(SqliteConfig(path=str(tmp_path / "oom.db")))
    await store.init()
    try:
        logger = AuditLogger(store=store)
        event = AuditEvent(
            actor="api-key:default",
            action="delete_user",
            target="user:u1",
            metadata={"tenant_id": "default"},
            created_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        )

        await logger.awrite(event)
        events = await store.list_audit_events("default")

        assert [item.action for item in events] == ["delete_user"]
        assert events[0].metadata["tenant_id"] == "default"
    finally:
        await store.close()
