"""Only-One-Memory 初始数据库结构迁移。"""

from __future__ import annotations

from alembic import op


revision = "20260519_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_events (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            session_key TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            event_ts TIMESTAMPTZ NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            search_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
            embedding VECTOR
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversation_events_search_tsv ON conversation_events USING GIN(search_tsv)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversation_events_scope ON conversation_events(tenant_id, user_id, agent_id, session_id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            session_key TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT NOT NULL,
            priority INTEGER NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            scene_name TEXT,
            source_event_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            timestamps JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            search_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
            embedding VECTOR
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_memories_search_tsv ON memories USING GIN(search_tsv)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(tenant_id, user_id, agent_id, session_id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_sources (
            memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
            event_id TEXT NOT NULL,
            PRIMARY KEY(memory_id, event_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scenes (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT NOT NULL,
            heat INTEGER NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL,
            UNIQUE(tenant_id, user_id, filename)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            tenant_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY(tenant_id, scope, scope_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS offload_entries (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            agent_id TEXT NOT NULL DEFAULT '',
            session_id TEXT NOT NULL,
            tool_call_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            summary TEXT NOT NULL,
            score INTEGER NOT NULL,
            node_id TEXT NOT NULL,
            result_ref TEXT NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_offload_entries_session ON offload_entries(tenant_id, session_id, created_at)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            session_key TEXT NOT NULL,
            run_after TIMESTAMPTZ NOT NULL,
            locked_by TEXT,
            locked_at TIMESTAMPTZ,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_claim ON pipeline_jobs(status, run_after, stage)")


def downgrade() -> None:
    for table in (
        "pipeline_jobs",
        "audit_logs",
        "offload_entries",
        "profiles",
        "scenes",
        "memory_sources",
        "memories",
        "conversation_events",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
