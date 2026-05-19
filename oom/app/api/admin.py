from fastapi import APIRouter, Depends, HTTPException, Request

from oom.app.dependencies import get_memory_core
from oom.app.security import require_api_key
from oom.memory_core.admin.delete_user import DeleteUserRequest, DeleteUserResult, DeleteUserService
from oom.memory_core.admin.export_import import ExportRequest, ImportResult, MemoryExport, MemoryExportImportService
from oom.memory_core.config import AppConfig
from oom.memory_core.core import MemoryCore
from oom.memory_core.offload.ref_store import OffloadRefStore

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/admin/pipeline/status")
async def pipeline_status(core: MemoryCore = Depends(get_memory_core)) -> dict[str, object]:
    return core.pipeline_status()


@router.post("/admin/reindex")
async def reindex(core: MemoryCore = Depends(get_memory_core)) -> dict[str, object]:
    return await core.reindex_all()


@router.post("/admin/export", response_model=MemoryExport)
async def export_memory(
    payload: ExportRequest,
    request: Request,
    core: MemoryCore = Depends(get_memory_core),
) -> MemoryExport:
    config = getattr(request.app.state, "config", AppConfig())
    refs = OffloadRefStore(config.offload.data_dir).list_ref_metadata(payload.tenant_id)
    service = MemoryExportImportService(core.store, pipeline_state=core.pipeline.dump_states())
    return await service.export_tenant(payload.tenant_id, offload_refs=refs)


@router.post("/admin/import", response_model=ImportResult)
async def import_memory(payload: MemoryExport, core: MemoryCore = Depends(get_memory_core)) -> ImportResult:
    service = MemoryExportImportService(core.store, pipeline_state=core.pipeline.dump_states())
    try:
        return await service.import_export(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/admin/delete-user", response_model=DeleteUserResult)
async def delete_user(
    payload: DeleteUserRequest,
    request: Request,
    core: MemoryCore = Depends(get_memory_core),
) -> DeleteUserResult:
    config = getattr(request.app.state, "config", AppConfig())
    service = DeleteUserService(core.store, ref_store=OffloadRefStore(config.offload.data_dir))
    return await service.delete_user(payload.tenant_id, payload.user_id)
