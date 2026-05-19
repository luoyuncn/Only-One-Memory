from oom.memory_core.stores.postgres_store import postgres_schema_comment_statements


def test_postgres_schema_comments_cover_conversation_events_columns():
    statements = postgres_schema_comment_statements()
    joined = "\n".join(statements)

    assert "COMMENT ON TABLE conversation_events" in joined
    for column in [
        "id",
        "tenant_id",
        "user_id",
        "agent_id",
        "session_id",
        "session_key",
        "role",
        "content",
        "event_ts",
        "recorded_at",
        "metadata_json",
        "search_tsv",
        "embedding",
    ]:
        assert f"COMMENT ON COLUMN conversation_events.{column}" in joined
