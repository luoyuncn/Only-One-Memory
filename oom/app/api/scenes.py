"""场景 API，管理 L2 scene Markdown 块。"""

from fastapi import APIRouter, Depends, HTTPException

from oom.app.dependencies import get_memory_core
from oom.memory_core.core import MemoryCore
from oom.memory_core.types import SceneBlock, SceneListResult, ScenePatchRequest

router = APIRouter()


@router.get("/scenes", response_model=SceneListResult)
async def list_scenes(tenant_id: str, user_id: str, core: MemoryCore = Depends(get_memory_core)) -> SceneListResult:
    return await core.list_scenes(tenant_id=tenant_id, user_id=user_id)


@router.get("/scenes/{scene_id}", response_model=SceneBlock)
async def get_scene(scene_id: str, tenant_id: str, core: MemoryCore = Depends(get_memory_core)) -> SceneBlock:
    scene = await core.get_scene(scene_id=scene_id, tenant_id=tenant_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="scene not found")
    return scene


@router.patch("/scenes/{scene_id}", response_model=SceneBlock)
async def patch_scene(
    scene_id: str, request: ScenePatchRequest, core: MemoryCore = Depends(get_memory_core)
) -> SceneBlock:
    return await core.patch_scene(scene_id=scene_id, request=request)
