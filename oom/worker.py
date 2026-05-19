from __future__ import annotations

import asyncio
import os

from oom.memory_core.pipeline.jobs import PipelineJobStore
from oom.memory_core.pipeline.scheduler import PipelineScheduler


async def _noop_handler(session_key: str, payload: dict) -> None:
    return None


async def main() -> None:
    dsn = os.environ["OOM_POSTGRES_DSN"]
    store = PipelineJobStore(dsn)
    await store.init()
    scheduler = PipelineScheduler(store, worker_id=os.getenv("OOM_WORKER_ID", "worker-1"), handlers={"l1": _noop_handler})
    await scheduler.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
