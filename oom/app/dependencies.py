from __future__ import annotations

from fastapi import Request

from oom.memory_core.config import AppConfig
from oom.memory_core.core import MemoryCore


async def get_memory_core(request: Request) -> MemoryCore:
    core = getattr(request.app.state, "memory_core", None)
    if core is None:
        core = MemoryCore(AppConfig())
        request.app.state.memory_core = core
    await core.initialize()
    return core
