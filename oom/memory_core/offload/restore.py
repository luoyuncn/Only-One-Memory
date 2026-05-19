from __future__ import annotations

from oom.memory_core.offload.ref_store import OffloadRefStore
from oom.memory_core.offload.types import RestoreOffloadResult


class OffloadRestoreService:
    def __init__(self, ref_store: OffloadRefStore) -> None:
        self.ref_store = ref_store

    def restore_by_ref(self, result_ref: str, *, tenant_id: str, session_id: str) -> RestoreOffloadResult:
        ref = self.ref_store.get_ref(result_ref)
        if ref is None:
            raise KeyError(result_ref)
        if ref.tenant_id != tenant_id or ref.session_id != session_id:
            raise KeyError(result_ref)
        return RestoreOffloadResult(raw_content=ref.content, result_ref=ref.id, metadata=ref.metadata)
