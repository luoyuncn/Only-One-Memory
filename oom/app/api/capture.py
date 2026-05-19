from fastapi import APIRouter, Depends, HTTPException

from oom.app.dependencies import get_memory_core
from oom.memory_core.core import MemoryCore
from oom.memory_core.types import CaptureResult, CaptureTurnRequest

router = APIRouter()


@router.post("/capture/turn", response_model=CaptureResult)
async def capture_turn(request: CaptureTurnRequest, core: MemoryCore = Depends(get_memory_core)) -> CaptureResult:
    try:
        return await core.commit_turn(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
