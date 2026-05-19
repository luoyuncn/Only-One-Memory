"""租户级导出/导入服务，用于备份、迁移和恢复记忆数据。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from oom.memory_core.admin.audit import AuditEvent, AuditLogger


class MemoryExport(BaseModel):
    """租户导出文件的顶层格式。"""

    version: int = 1
    tenant_id: str
    records: dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    tenant_id: str = "default"


class ImportResult(BaseModel):
    tenant_id: str
    imported: dict[str, int] = Field(default_factory=dict)


class MemoryExportImportService:
    """导入导出编排器，把 store 数据、offload refs 和 pipeline state 汇总在一起。"""

    def __init__(self, store, pipeline_state: dict[str, Any] | None = None) -> None:
        self.store = store
        self.pipeline_state = pipeline_state or {}
        self.audit = AuditLogger(store=store)

    async def export_tenant(self, tenant_id: str, offload_refs: list[dict[str, Any]] | None = None) -> MemoryExport:
        """导出租户记录并追加导出审计事件。"""
        records = await self.store.export_tenant_records(tenant_id)
        records["offload_refs"] = offload_refs or []
        records["pipeline_state"] = self.pipeline_state
        await self.audit.awrite(
            AuditEvent(
                actor="api-key:default",
                action="export",
                target=f"tenant:{tenant_id}",
                metadata={"tenant_id": tenant_id},
            )
        )
        records["audit"] = [event.model_dump(mode="json") for event in await self.store.list_audit_events(tenant_id)]
        return MemoryExport(version=1, tenant_id=tenant_id, records=records)

    async def import_export(self, payload: MemoryExport) -> ImportResult:
        """导入导出包，当前只接受 version=1。"""
        if payload.version != 1:
            raise ValueError("unsupported export version")
        imported = await self.store.import_tenant_records(payload.tenant_id, payload.records)
        await self.audit.awrite(
            AuditEvent(
                actor="api-key:default",
                action="import",
                target=f"tenant:{payload.tenant_id}",
                metadata={"tenant_id": payload.tenant_id, "version": payload.version},
            )
        )
        return ImportResult(tenant_id=payload.tenant_id, imported=imported)
