"""FastAPI 依赖注入，把请求路由连接到共享 MemoryCore 实例。"""

from __future__ import annotations

from fastapi import Request

from oom.memory_core.config import AppConfig
from oom.memory_core.core import MemoryCore


async def get_memory_core(request: Request) -> MemoryCore:
    """为整个 FastAPI app 复用一个 MemoryCore 实例。"""
    core = getattr(request.app.state, "memory_core", None)
    if core is None:
        config = getattr(request.app.state, "config", AppConfig())
        core = MemoryCore(config)
        request.app.state.memory_core = core
    await core.initialize()
    return core
