from fastapi import APIRouter, Depends

from oom.app.dependencies import get_memory_core
from oom.memory_core.core import MemoryCore
from oom.memory_core.types import RecallBeforeRequest, RecallBeforeResult

router = APIRouter()


@router.post("/recall/before", response_model=RecallBeforeResult)
async def recall_before(
    request: RecallBeforeRequest, core: MemoryCore = Depends(get_memory_core)
) -> RecallBeforeResult:
    return await core.before_recall(request)
