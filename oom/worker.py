from __future__ import annotations

import asyncio
import os

from oom.memory_core.config import AppConfig
from oom.memory_core.core import MemoryCore
from oom.memory_core.pipeline.jobs import PipelineJobStore
from oom.memory_core.pipeline.scheduler import PipelineScheduler


async def _l1_handler(core: MemoryCore, session_key: str, payload: dict) -> None:
    await core.flush_l1_session(session_key)


async def main() -> None:
    dsn = os.environ["OOM_POSTGRES_DSN"]
    store = PipelineJobStore(dsn)
    await store.init()
    core = MemoryCore(AppConfig())
    try:
        scheduler = PipelineScheduler(
            store,
            worker_id=os.getenv("OOM_WORKER_ID", "worker-1"),
            handlers={"l1": lambda session_key, payload: _l1_handler(core, session_key, payload)},
        )
        await scheduler.run_forever()
    finally:
        await core.close()


if __name__ == "__main__":
    asyncio.run(main())
