from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from oom.memory_core.pipeline.jobs import PipelineJobStore


JobHandler = Callable[[str, dict], Awaitable[object]]


class PipelineScheduler:
    def __init__(self, job_store: PipelineJobStore, worker_id: str, handlers: dict[str, JobHandler]) -> None:
        self.job_store = job_store
        self.worker_id = worker_id
        self.handlers = handlers

    async def run_once(self) -> bool:
        job = await self.job_store.claim_next(self.worker_id)
        if job is None:
            return False
        handler = self.handlers.get(job.stage)
        try:
            if handler is not None:
                await handler(job.session_key, job.payload)
        except Exception:
            await self.job_store.fail(job.id)
            raise
        await self.job_store.complete(job.id)
        return True

    async def run_forever(self, poll_interval_seconds: float = 1.0) -> None:
        while True:
            handled = await self.run_once()
            if not handled:
                await asyncio.sleep(poll_interval_seconds)
