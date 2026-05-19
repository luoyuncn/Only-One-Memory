from __future__ import annotations

import json
import math
from typing import Any

import aiosqlite

from oom.memory_core.config import SqliteConfig
from oom.memory_core.types import ConversationSearchHit, L0Event, MemoryAtom, MemorySearchHit, StoreCapabilities


class SqliteMemoryStore:
    def __init__(self, config: SqliteConfig) -> None:
        self.config = config
        self.vector_backend = config.vector_backend
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self.config.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._try_enable_sqlite_vec()
        await self._db.executescript(
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
                event_ts TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS conversation_events_fts
            USING fts5(event_id UNINDEXED, content);

            CREATE TABLE IF NOT EXISTS l0_embeddings (
                event_id TEXT PRIMARY KEY,
                embedding_json TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES conversation_events(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_conversation_events_scope
            ON conversation_events(tenant_id, user_id, agent_id, session_id);

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
                confidence REAL NOT NULL,
                scene_name TEXT,
                source_event_ids_json TEXT NOT NULL DEFAULT '[]',
                timestamps_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(memory_id UNINDEXED, content);

            CREATE TABLE IF NOT EXISTS l1_embeddings (
                memory_id TEXT PRIMARY KEY,
                embedding_json TEXT NOT NULL,
                FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memory_sources (
                memory_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                PRIMARY KEY(memory_id, event_id),
                FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_memories_scope
            ON memories(tenant_id, user_id, agent_id, session_id);
            """
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    def capabilities(self) -> StoreCapabilities:
        return StoreCapabilities(
            backend="sqlite",
            fts_search=True,
            vector_search=True,
            vector_backend=self.vector_backend,
        )

    async def upsert_l0(self, event: L0Event, embedding: list[float] | None = None) -> bool:
        db = self._require_db()
        await db.execute(
            """
            INSERT INTO conversation_events (
                id, tenant_id, user_id, agent_id, session_id, session_key, role,
                content, event_ts, recorded_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                metadata_json = excluded.metadata_json
            """,
            (
                event.id,
                event.tenant_id,
                event.user_id,
                event.agent_id,
                event.session_id,
                event.session_key,
                event.role,
                event.content,
                event.event_ts.isoformat(),
                event.recorded_at.isoformat(),
                json.dumps(event.metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        await db.execute("DELETE FROM conversation_events_fts WHERE event_id = ?", (event.id,))
        await db.execute("INSERT INTO conversation_events_fts(event_id, content) VALUES (?, ?)", (event.id, event.content))
        if embedding is not None:
            await db.execute(
                """
                INSERT INTO l0_embeddings(event_id, embedding_json)
                VALUES (?, ?)
                ON CONFLICT(event_id) DO UPDATE SET embedding_json = excluded.embedding_json
                """,
                (event.id, json.dumps(embedding)),
            )
        await db.commit()
        return True

    async def search_l0_fts(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[ConversationSearchHit]:
        db = self._require_db()
        where_sql, params = self._filters_sql(filters)
        try:
            cursor = await db.execute(
                f"""
                SELECT e.*, bm25(conversation_events_fts) AS rank
                FROM conversation_events_fts
                JOIN conversation_events e ON e.id = conversation_events_fts.event_id
                WHERE conversation_events_fts MATCH ?{where_sql}
                ORDER BY rank
                LIMIT ?
                """,
                [query, *params, limit],
            )
            rows = await cursor.fetchall()
        except aiosqlite.OperationalError:
            rows = []

        if not rows:
            rows = await self._search_l0_like(query, limit, filters)
            return [ConversationSearchHit(event=self._event_from_row(row), score=1.0) for row in rows]

        return [ConversationSearchHit(event=self._event_from_row(row), score=float(-row["rank"])) for row in rows]

    async def search_l0_vector(
        self, embedding: list[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[ConversationSearchHit]:
        db = self._require_db()
        where_sql, params = self._filters_sql(filters)
        cursor = await db.execute(
            f"""
            SELECT e.*, le.embedding_json
            FROM l0_embeddings le
            JOIN conversation_events e ON e.id = le.event_id
            WHERE 1 = 1{where_sql}
            """,
            params,
        )
        rows = await cursor.fetchall()
        scored = []
        for row in rows:
            stored_embedding = json.loads(row["embedding_json"])
            scored.append((self._cosine_similarity(embedding, stored_embedding), row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            ConversationSearchHit(event=self._event_from_row(row), score=float(score))
            for score, row in scored[:limit]
        ]

    async def query_l0_for_l1(self, filters: dict[str, Any] | None = None, limit: int = 100) -> list[L0Event]:
        db = self._require_db()
        where_sql, params = self._filters_sql(filters)
        cursor = await db.execute(
            f"""
            SELECT *
            FROM conversation_events e
            WHERE 1 = 1{where_sql}
            ORDER BY event_ts ASC
            LIMIT ?
            """,
            [*params, limit],
        )
        rows = await cursor.fetchall()
        return [self._event_from_row(row) for row in rows]

    async def upsert_l1(self, memory: MemoryAtom, embedding: list[float] | None = None) -> bool:
        db = self._require_db()
        await db.execute(
            """
            INSERT INTO memories (
                id, tenant_id, user_id, agent_id, session_id, session_key, content, type,
                priority, confidence, scene_name, source_event_ids_json, timestamps_json,
                metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                source_event_ids_json = excluded.source_event_ids_json,
                timestamps_json = excluded.timestamps_json,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
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
                memory.created_at.isoformat(),
                memory.updated_at.isoformat(),
            ),
        )
        await db.execute("DELETE FROM memories_fts WHERE memory_id = ?", (memory.id,))
        await db.execute("INSERT INTO memories_fts(memory_id, content) VALUES (?, ?)", (memory.id, memory.content))
        await db.execute("DELETE FROM memory_sources WHERE memory_id = ?", (memory.id,))
        await db.executemany(
            "INSERT INTO memory_sources(memory_id, event_id) VALUES (?, ?)",
            [(memory.id, event_id) for event_id in memory.source_event_ids],
        )
        if embedding is not None:
            await db.execute(
                """
                INSERT INTO l1_embeddings(memory_id, embedding_json)
                VALUES (?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET embedding_json = excluded.embedding_json
                """,
                (memory.id, json.dumps(embedding)),
            )
        await db.commit()
        return True

    async def search_l1_fts(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[MemorySearchHit]:
        db = self._require_db()
        where_sql, params = self._filters_sql(filters, alias="m")
        try:
            cursor = await db.execute(
                f"""
                SELECT m.*, bm25(memories_fts) AS rank
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.memory_id
                WHERE memories_fts MATCH ?{where_sql}
                ORDER BY rank
                LIMIT ?
                """,
                [query, *params, limit],
            )
            rows = await cursor.fetchall()
        except aiosqlite.OperationalError:
            rows = []

        if not rows:
            rows = await self._search_l1_like(query, limit, filters)
            return [MemorySearchHit(memory=self._memory_from_row(row), score=1.0) for row in rows]

        return [MemorySearchHit(memory=self._memory_from_row(row), score=float(-row["rank"])) for row in rows]

    async def search_l1_vector(
        self, embedding: list[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[MemorySearchHit]:
        db = self._require_db()
        where_sql, params = self._filters_sql(filters, alias="m")
        cursor = await db.execute(
            f"""
            SELECT m.*, le.embedding_json
            FROM l1_embeddings le
            JOIN memories m ON m.id = le.memory_id
            WHERE 1 = 1{where_sql}
            """,
            params,
        )
        rows = await cursor.fetchall()
        scored = []
        for row in rows:
            stored_embedding = json.loads(row["embedding_json"])
            scored.append((self._cosine_similarity(embedding, stored_embedding), row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [MemorySearchHit(memory=self._memory_from_row(row), score=float(score)) for score, row in scored[:limit]]

    async def _try_enable_sqlite_vec(self) -> None:
        if self._db is None:
            return
        try:
            import sqlite_vec

            await self._db.enable_load_extension(True)
            await self._db.execute("SELECT load_extension(?)", (sqlite_vec.loadable_path(),))
            await self._db.enable_load_extension(False)
            self.vector_backend = "sqlite_vec"
        except Exception:
            self.vector_backend = "blob_bruteforce"

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SQLite memory store is not initialized")
        return self._db

    @staticmethod
    def _filters_sql(filters: dict[str, Any] | None, alias: str = "e") -> tuple[str, list[Any]]:
        if not filters:
            return "", []
        allowed = {"tenant_id", "user_id", "agent_id", "session_id", "session_key", "role"}
        clauses = []
        params: list[Any] = []
        for key, value in filters.items():
            if key in allowed and value is not None:
                clauses.append(f" AND {alias}.{key} = ?")
                params.append(value)
        return "".join(clauses), params

    async def _search_l0_like(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[aiosqlite.Row]:
        db = self._require_db()
        where_sql, params = self._filters_sql(filters)
        tokens = [token for token in query.split() if token]
        like_sql = "".join(" AND e.content LIKE ?" for _ in tokens)
        like_params = [f"%{token}%" for token in tokens]
        cursor = await db.execute(
            f"""
            SELECT e.*, 0.0 AS rank
            FROM conversation_events e
            WHERE 1 = 1{where_sql}{like_sql}
            ORDER BY e.event_ts DESC
            LIMIT ?
            """,
            [*params, *like_params, limit],
        )
        return list(await cursor.fetchall())

    async def _search_l1_like(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[aiosqlite.Row]:
        db = self._require_db()
        where_sql, params = self._filters_sql(filters, alias="m")
        tokens = [token for token in query.split() if token]
        like_sql = "".join(" AND m.content LIKE ?" for _ in tokens)
        like_params = [f"%{token}%" for token in tokens]
        cursor = await db.execute(
            f"""
            SELECT m.*, 0.0 AS rank
            FROM memories m
            WHERE 1 = 1{where_sql}{like_sql}
            ORDER BY m.updated_at DESC
            LIMIT ?
            """,
            [*params, *like_params, limit],
        )
        return list(await cursor.fetchall())

    @staticmethod
    def _event_from_row(row: aiosqlite.Row) -> L0Event:
        return L0Event.model_validate(
            {
                "id": row["id"],
                "tenant_id": row["tenant_id"],
                "user_id": row["user_id"],
                "agent_id": row["agent_id"],
                "session_id": row["session_id"],
                "session_key": row["session_key"],
                "role": row["role"],
                "content": row["content"],
                "event_ts": row["event_ts"],
                "recorded_at": row["recorded_at"],
                "metadata": json.loads(row["metadata_json"]),
            }
        )

    @staticmethod
    def _memory_from_row(row: aiosqlite.Row) -> MemoryAtom:
        return MemoryAtom.model_validate(
            {
                "id": row["id"],
                "tenant_id": row["tenant_id"],
                "user_id": row["user_id"],
                "agent_id": row["agent_id"],
                "session_id": row["session_id"],
                "session_key": row["session_key"],
                "content": row["content"],
                "type": row["type"],
                "priority": row["priority"],
                "confidence": row["confidence"],
                "scene_name": row["scene_name"],
                "source_event_ids": json.loads(row["source_event_ids_json"]),
                "timestamps": json.loads(row["timestamps_json"]),
                "metadata": json.loads(row["metadata_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)
