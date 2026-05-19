from __future__ import annotations

import json
from typing import Any

import asyncpg

from oom.memory_core.config import PostgresConfig
from oom.memory_core.types import ConversationSearchHit, L0Event, MemoryAtom, MemorySearchHit, StoreCapabilities


def postgres_schema_comment_statements() -> tuple[str, ...]:
    return (
        "COMMENT ON TABLE conversation_events IS 'L0 原始对话事件表，保存 user/assistant/tool/system 的原文事件'",
        "COMMENT ON COLUMN conversation_events.id IS '事件唯一 ID'",
        "COMMENT ON COLUMN conversation_events.tenant_id IS '租户 ID，用于多租户隔离'",
        "COMMENT ON COLUMN conversation_events.user_id IS '用户 ID'",
        "COMMENT ON COLUMN conversation_events.agent_id IS 'Agent ID'",
        "COMMENT ON COLUMN conversation_events.session_id IS '会话 ID'",
        "COMMENT ON COLUMN conversation_events.session_key IS '外部稳定会话键，通常由 agent/user/session 组合生成'",
        "COMMENT ON COLUMN conversation_events.role IS '消息角色：system/user/assistant/tool'",
        "COMMENT ON COLUMN conversation_events.content IS '原始消息内容'",
        "COMMENT ON COLUMN conversation_events.event_ts IS '事件发生时间'",
        "COMMENT ON COLUMN conversation_events.recorded_at IS '写入 OOM 的记录时间'",
        "COMMENT ON COLUMN conversation_events.metadata_json IS '事件扩展元数据 JSON'",
        "COMMENT ON COLUMN conversation_events.search_tsv IS '由 content 生成的全文检索向量'",
        "COMMENT ON COLUMN conversation_events.embedding IS 'pgvector 向量，用于语义检索'",
    )


class PostgresMemoryStore:
    def __init__(self, config: PostgresConfig) -> None:
        self.config = config
        self._pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        if not self.config.dsn:
            raise ValueError("Postgres DSN is required")
        self._pool = await asyncpg.create_pool(dsn=self._normalize_dsn(self.config.dsn), min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(
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
                    embedding vector
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_events_search_tsv
                ON conversation_events USING GIN(search_tsv)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_events_scope
                ON conversation_events(tenant_id, user_id, agent_id, session_id)
                """
            )
            await conn.execute(
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
                    embedding vector
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_sources (
                    memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    event_id TEXT NOT NULL,
                    PRIMARY KEY(memory_id, event_id)
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_search_tsv
                ON memories USING GIN(search_tsv)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_scope
                ON memories(tenant_id, user_id, agent_id, session_id)
                """
            )
            for statement in postgres_schema_comment_statements():
                await conn.execute(statement)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def capabilities(self) -> StoreCapabilities:
        return StoreCapabilities(
            backend="postgres",
            fts_search=True,
            vector_search=True,
            vector_backend="pgvector",
        )

    async def upsert_l0(self, event: L0Event, embedding: list[float] | None = None) -> bool:
        pool = self._require_pool()
        embedding_literal = self._vector_literal(embedding) if embedding is not None else None
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_events (
                    id, tenant_id, user_id, agent_id, session_id, session_key, role,
                    content, event_ts, recorded_at, metadata_json, embedding
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12::vector)
                ON CONFLICT(id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    user_id = excluded.user_id,
                    agent_id = excluded.agent_id,
                    session_id = excluded.session_id,
                    session_key = excluded.session_key,
                    role = excluded.role,
                    content = excluded.content,
                    event_ts = excluded.event_ts,
                    recorded_at = excluded.recorded_at,
                    metadata_json = excluded.metadata_json,
                    embedding = excluded.embedding
                """,
                event.id,
                event.tenant_id,
                event.user_id,
                event.agent_id,
                event.session_id,
                event.session_key,
                event.role,
                event.content,
                event.event_ts,
                event.recorded_at,
                json.dumps(event.metadata, ensure_ascii=False, sort_keys=True),
                embedding_literal,
            )
        return True

    async def search_l0_fts(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[ConversationSearchHit]:
        pool = self._require_pool()
        where_sql, params = self._filters_sql(filters, start_index=3)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT *, ts_rank(search_tsv, plainto_tsquery('simple', $1)) AS score
                FROM conversation_events e
                WHERE search_tsv @@ plainto_tsquery('simple', $1){where_sql}
                ORDER BY score DESC, event_ts DESC
                LIMIT $2
                """,
                query,
                limit,
                *params,
            )
        return [ConversationSearchHit(event=self._event_from_record(row), score=float(row["score"])) for row in rows]

    async def search_l0_vector(
        self, embedding: list[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[ConversationSearchHit]:
        pool = self._require_pool()
        where_sql, params = self._filters_sql(filters, start_index=3)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT *, 1 - (embedding <=> $1::vector) AS score
                FROM conversation_events e
                WHERE embedding IS NOT NULL{where_sql}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                self._vector_literal(embedding),
                limit,
                *params,
            )
        return [ConversationSearchHit(event=self._event_from_record(row), score=float(row["score"])) for row in rows]

    async def query_l0_for_l1(self, filters: dict[str, Any] | None = None, limit: int = 100) -> list[L0Event]:
        pool = self._require_pool()
        where_sql, params = self._filters_sql(filters, start_index=2)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT *
                FROM conversation_events e
                WHERE 1 = 1{where_sql}
                ORDER BY event_ts ASC
                LIMIT $1
                """,
                limit,
                *params,
            )
        return [self._event_from_record(row) for row in rows]

    async def upsert_l1(self, memory: MemoryAtom, embedding: list[float] | None = None) -> bool:
        pool = self._require_pool()
        embedding_literal = self._vector_literal(embedding) if embedding is not None else None
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO memories (
                        id, tenant_id, user_id, agent_id, session_id, session_key, content, type,
                        priority, confidence, scene_name, source_event_ids, timestamps,
                        metadata_json, created_at, updated_at, embedding
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                        $12::jsonb, $13::jsonb, $14::jsonb, $15, $16, $17::vector
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        tenant_id = excluded.tenant_id,
                        user_id = excluded.user_id,
                        agent_id = excluded.agent_id,
                        session_id = excluded.session_id,
                        session_key = excluded.session_key,
                        content = excluded.content,
                        type = excluded.type,
                        priority = excluded.priority,
                        confidence = excluded.confidence,
                        scene_name = excluded.scene_name,
                        source_event_ids = excluded.source_event_ids,
                        timestamps = excluded.timestamps,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at,
                        embedding = excluded.embedding
                    """,
                    memory.id,
                    memory.tenant_id,
                    memory.user_id,
                    memory.agent_id,
                    memory.session_id,
                    memory.session_key,
                    memory.content,
                    memory.type,
                    memory.priority,
                    memory.confidence,
                    memory.scene_name,
                    json.dumps(memory.source_event_ids, ensure_ascii=False),
                    json.dumps(memory.timestamps, ensure_ascii=False),
                    json.dumps(memory.metadata, ensure_ascii=False, sort_keys=True),
                    memory.created_at,
                    memory.updated_at,
                    embedding_literal,
                )
                await conn.execute("DELETE FROM memory_sources WHERE memory_id = $1", memory.id)
                await conn.executemany(
                    "INSERT INTO memory_sources(memory_id, event_id) VALUES ($1, $2)",
                    [(memory.id, event_id) for event_id in memory.source_event_ids],
                )
        return True

    async def search_l1_fts(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[MemorySearchHit]:
        pool = self._require_pool()
        where_sql, params = self._filters_sql(filters, start_index=3, alias="m")
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT *, ts_rank(search_tsv, plainto_tsquery('simple', $1)) AS score
                FROM memories m
                WHERE search_tsv @@ plainto_tsquery('simple', $1){where_sql}
                ORDER BY score DESC, updated_at DESC
                LIMIT $2
                """,
                query,
                limit,
                *params,
            )
        return [MemorySearchHit(memory=self._memory_from_record(row), score=float(row["score"])) for row in rows]

    async def search_l1_vector(
        self, embedding: list[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[MemorySearchHit]:
        pool = self._require_pool()
        where_sql, params = self._filters_sql(filters, start_index=3, alias="m")
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT *, 1 - (embedding <=> $1::vector) AS score
                FROM memories m
                WHERE embedding IS NOT NULL{where_sql}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                self._vector_literal(embedding),
                limit,
                *params,
            )
        return [MemorySearchHit(memory=self._memory_from_record(row), score=float(row["score"])) for row in rows]

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Postgres memory store is not initialized")
        return self._pool

    @staticmethod
    def _normalize_dsn(dsn: str) -> str:
        return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    @staticmethod
    def _vector_literal(embedding: list[float] | None) -> str | None:
        if embedding is None:
            return None
        return "[" + ",".join(str(float(value)) for value in embedding) + "]"

    @staticmethod
    def _filters_sql(filters: dict[str, Any] | None, start_index: int, alias: str = "e") -> tuple[str, list[Any]]:
        if not filters:
            return "", []
        allowed = {"tenant_id", "user_id", "agent_id", "session_id", "session_key", "role"}
        clauses = []
        params: list[Any] = []
        index = start_index
        for key, value in filters.items():
            if key in allowed and value is not None:
                clauses.append(f" AND {alias}.{key} = ${index}")
                params.append(value)
                index += 1
        return "".join(clauses), params

    @staticmethod
    def _event_from_record(record: asyncpg.Record) -> L0Event:
        metadata = record["metadata_json"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return L0Event.model_validate(
            {
                "id": record["id"],
                "tenant_id": record["tenant_id"],
                "user_id": record["user_id"],
                "agent_id": record["agent_id"],
                "session_id": record["session_id"],
                "session_key": record["session_key"],
                "role": record["role"],
                "content": record["content"],
                "event_ts": record["event_ts"],
                "recorded_at": record["recorded_at"],
                "metadata": metadata,
            }
        )

    @staticmethod
    def _memory_from_record(record: asyncpg.Record) -> MemoryAtom:
        source_event_ids = record["source_event_ids"]
        timestamps = record["timestamps"]
        metadata = record["metadata_json"]
        if isinstance(source_event_ids, str):
            source_event_ids = json.loads(source_event_ids)
        if isinstance(timestamps, str):
            timestamps = json.loads(timestamps)
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return MemoryAtom.model_validate(
            {
                "id": record["id"],
                "tenant_id": record["tenant_id"],
                "user_id": record["user_id"],
                "agent_id": record["agent_id"],
                "session_id": record["session_id"],
                "session_key": record["session_key"],
                "content": record["content"],
                "type": record["type"],
                "priority": record["priority"],
                "confidence": record["confidence"],
                "scene_name": record["scene_name"],
                "source_event_ids": source_event_ids,
                "timestamps": timestamps,
                "metadata": metadata,
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
            }
        )
