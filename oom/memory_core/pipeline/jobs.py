"""Postgres 后台任务队列，支持 worker claim/complete/fail 生命周期。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import asyncpg


@dataclass(frozen=True)
class PipelineJob:
    """worker 领取到的一条后台任务快照。"""

    id: str
    stage: str
    session_key: str
    payload: dict[str, Any]
    locked_by: str | None


class PipelineJobStore:
    """基于 Postgres 的轻量任务队列。

    `claim_next` 使用 `FOR UPDATE SKIP LOCKED`，因此多个 worker 可以并发领取任务而不互相阻塞。
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = self._normalize_dsn(dsn)
        self._pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        self._pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute(
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
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_claim
                ON pipeline_jobs(status, run_after, stage)
                """
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def enqueue(self, stage: str, session_key: str, payload: dict[str, Any]) -> str:
        """写入 pending 任务，默认立即可运行。"""
        pool = self._require_pool()
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pipeline_jobs(id, status, stage, session_key, run_after, payload, created_at)
                VALUES ($1, 'pending', $2, $3, $4, $5::jsonb, $6)
                """,
                job_id,
                stage,
                session_key,
                now,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                now,
            )
        return job_id

    async def claim_next(self, worker_id: str) -> PipelineJob | None:
        """原子领取下一条可运行任务，并标记 running/locked_by。"""
        pool = self._require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM pipeline_jobs
                    WHERE status = 'pending' AND run_after <= now()
                    ORDER BY run_after ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                )
                if row is None:
                    return None
                await conn.execute(
                    """
                    UPDATE pipeline_jobs
                    SET status = 'running', locked_by = $2, locked_at = now()
                    WHERE id = $1
                    """,
                    row["id"],
                    worker_id,
                )
                payload = row["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                return PipelineJob(
                    id=row["id"],
                    stage=row["stage"],
                    session_key=row["session_key"],
                    payload=dict(payload),
                    locked_by=worker_id,
                )

    async def complete(self, job_id: str) -> None:
        await self._set_status(job_id, "completed")

    async def fail(self, job_id: str) -> None:
        await self._set_status(job_id, "failed")

    async def _set_status(self, job_id: str, status: str) -> None:
        """结束任务生命周期，同时释放锁字段。"""
        pool = self._require_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_jobs
                SET status = $2, locked_by = NULL, locked_at = NULL
                WHERE id = $1
                """,
                job_id,
                status,
            )

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PipelineJobStore is not initialized")
        return self._pool

    @staticmethod
    def _normalize_dsn(dsn: str) -> str:
        return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
