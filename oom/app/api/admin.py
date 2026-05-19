from fastapi import APIRouter, Depends

from oom.app.dependencies import get_memory_core
from oom.memory_core.core import MemoryCore

router = APIRouter()


@router.get("/admin/pipeline/status")
async def pipeline_status(core: MemoryCore = Depends(get_memory_core)) -> dict[str, object]:
    return core.pipeline_status()


@router.post("/admin/reindex")
async def reindex(core: MemoryCore = Depends(get_memory_core)) -> dict[str, object]:
    return await core.reindex_all()
