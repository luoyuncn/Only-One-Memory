from typing import cast

from oom.memory_core.pipeline.jobs import PipelineJob, PipelineJobStore
from oom.memory_core.pipeline.scheduler import PipelineScheduler


class FakeJobStore:
    def __init__(self):
        self.job = PipelineJob(id="j1", stage="l1", session_key="s1", payload={}, locked_by=None)
        self.completed = []
        self.failed = []

    async def claim_next(self, worker_id: str):
        job = self.job
        self.job = None
        return job

    async def complete(self, job_id: str):
        self.completed.append(job_id)

    async def fail(self, job_id: str):
        self.failed.append(job_id)


async def test_scheduler_completes_successful_job():
    store = FakeJobStore()
    calls = []

    async def handler(session_key: str, payload: dict):
        calls.append(session_key)

    scheduler = PipelineScheduler(cast(PipelineJobStore, store), worker_id="w1", handlers={"l1": handler})

    assert await scheduler.run_once() is True
    assert calls == ["s1"]
    assert store.completed == ["j1"]
    assert store.failed == []
