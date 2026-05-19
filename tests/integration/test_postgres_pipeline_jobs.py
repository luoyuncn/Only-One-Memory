import os

import pytest

from oom.memory_core.pipeline.jobs import PipelineJobStore


pytestmark = pytest.mark.skipif(
    not os.getenv("OOM_POSTGRES_DSN"),
    reason="OOM_POSTGRES_DSN is required for Postgres job tests",
)


async def test_claim_job_uses_single_owner():
    store = PipelineJobStore(os.environ["OOM_POSTGRES_DSN"])
    await store.init()
    await store.enqueue(stage="l1", session_key="s1", payload={"session_key": "s1"})

    first = await store.claim_next(worker_id="w1")
    second = await store.claim_next(worker_id="w2")

    assert first is not None
    assert second is None
    await store.complete(first.id)
    await store.close()
