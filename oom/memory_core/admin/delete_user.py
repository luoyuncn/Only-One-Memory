from __future__ import annotations

from pydantic import BaseModel, Field

from oom.memory_core.admin.audit import AuditEvent, AuditLogger


class DeleteUserPlan(BaseModel):
    tenant_id: str
    user_id: str
    layers: list[str] = Field(default_factory=list)

    @classmethod
    def for_user(cls, tenant_id: str, user_id: str) -> "DeleteUserPlan":
        return cls(
            tenant_id=tenant_id,
            user_id=user_id,
            layers=["l0", "l1", "l2", "l3", "offload", "indexes", "audit"],
        )


class DeleteUserRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str


class DeleteUserResult(BaseModel):
    plan: DeleteUserPlan
    deleted: dict[str, int]


class DeleteUserService:
    def __init__(self, store, ref_store=None) -> None:
        self.store = store
        self.ref_store = ref_store
        self.audit = AuditLogger(store=store)

    async def delete_user(self, tenant_id: str, user_id: str) -> DeleteUserResult:
        plan = DeleteUserPlan.for_user(tenant_id, user_id)
        deleted = await self.store.delete_user_records(tenant_id, user_id)
        if self.ref_store is not None:
            deleted["offload_refs"] = self.ref_store.delete_refs_for_user(tenant_id, user_id)
            deleted["offload"] = deleted.get("offload", 0) + deleted["offload_refs"]
        await self.audit.awrite(
            AuditEvent(
                actor="api-key:default",
                action="delete_user",
                target=f"user:{user_id}",
                metadata={"tenant_id": tenant_id, "user_id": user_id, "deleted": deleted},
            )
        )
        return DeleteUserResult(plan=plan, deleted=deleted)
