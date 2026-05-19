from fastapi import APIRouter, Depends, HTTPException

from oom.app.dependencies import get_memory_core
from oom.memory_core.core import MemoryCore
from oom.memory_core.types import ProfileDocument, ProfilePatchRequest

router = APIRouter()


@router.get("/profiles/{scope}/{scope_id}", response_model=ProfileDocument)
async def get_profile(
    scope: str, scope_id: str, tenant_id: str, core: MemoryCore = Depends(get_memory_core)
) -> ProfileDocument:
    profile = await core.get_profile(tenant_id=tenant_id, scope=scope, scope_id=scope_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return profile


@router.patch("/profiles/{scope}/{scope_id}", response_model=ProfileDocument)
async def patch_profile(
    scope: str, scope_id: str, request: ProfilePatchRequest, core: MemoryCore = Depends(get_memory_core)
) -> ProfileDocument:
    return await core.patch_profile(scope=scope, scope_id=scope_id, request=request)
