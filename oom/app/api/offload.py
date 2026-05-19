from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from oom.app.dependencies import get_memory_core
from oom.memory_core.config import AppConfig
from oom.memory_core.core import MemoryCore
from oom.memory_core.offload.mermaid_builder import build_mermaid_graph
from oom.memory_core.offload.ref_store import OffloadRefStore
from oom.memory_core.offload.restore import OffloadRestoreService
from oom.memory_core.offload.state_manager import build_offload_entry
from oom.memory_core.offload.types import (
    CreateOffloadEntryRequest,
    CreateOffloadRefRequest,
    OffloadEntry,
    OffloadRef,
    RestoreOffloadRequest,
    RestoreOffloadResult,
)
from oom.memory_core.observability.metrics import increment

router = APIRouter()


def _ref_store(request: Request) -> OffloadRefStore:
    store = getattr(request.app.state, "offload_ref_store", None)
    if store is None:
        config = AppConfig()
        store = OffloadRefStore(config.offload.data_dir)
        request.app.state.offload_ref_store = store
    return store


@router.post("/offload/refs", response_model=OffloadRef)
async def create_ref(payload: CreateOffloadRefRequest, request: Request) -> OffloadRef:
    return _ref_store(request).create_ref(**payload.model_dump())


@router.get("/offload/refs/{ref_id}", response_model=OffloadRef)
async def get_ref(ref_id: str, request: Request) -> OffloadRef:
    ref = _ref_store(request).get_ref(ref_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="offload ref not found")
    return ref


@router.post("/offload/restore", response_model=RestoreOffloadResult)
async def restore(
    payload: RestoreOffloadRequest,
    request: Request,
    core: MemoryCore = Depends(get_memory_core),
) -> RestoreOffloadResult:
    result_ref = payload.result_ref
    if result_ref is None and payload.node_id is not None:
        entries = await core.list_offload_entries(payload.tenant_id, payload.session_id)
        match = next((entry for entry in entries if entry.node_id == payload.node_id), None)
        if match is not None:
            result_ref = match.result_ref
    if result_ref is None:
        raise HTTPException(status_code=400, detail="result_ref or node_id is required")
    try:
        result = OffloadRestoreService(_ref_store(request)).restore_by_ref(result_ref)
        increment("oom_offload_restore_total")
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="offload ref not found") from exc


@router.post("/offload/entries", response_model=OffloadEntry)
async def create_entry(payload: CreateOffloadEntryRequest, core: MemoryCore = Depends(get_memory_core)) -> OffloadEntry:
    entry = build_offload_entry(
        tenant_id=payload.tenant_id,
        session_id=payload.session_id,
        tool_call_id=payload.tool_call_id,
        tool_name=payload.tool_name,
        summary=payload.summary,
        score=payload.score,
        node_id=payload.node_id,
        result_ref=payload.result_ref,
    ).model_copy(update={"metadata": payload.metadata})
    return await core.upsert_offload_entry(entry)


@router.get("/offload/entries", response_model=list[OffloadEntry])
async def list_entries(tenant_id: str, session_id: str, core: MemoryCore = Depends(get_memory_core)) -> list[OffloadEntry]:
    return await core.list_offload_entries(tenant_id, session_id)


@router.get("/offload/graph/{session_id}")
async def offload_graph(
    session_id: str, tenant_id: str = "default", core: MemoryCore = Depends(get_memory_core)
) -> dict[str, str]:
    return {"mermaid": build_mermaid_graph(await core.list_offload_entries(tenant_id, session_id))}
