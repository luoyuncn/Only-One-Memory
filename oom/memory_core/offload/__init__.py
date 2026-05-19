"""Context Offload 子系统，保存大块原文并提供可恢复引用。"""

from oom.memory_core.offload.ref_store import OffloadRefStore
from oom.memory_core.offload.types import OffloadRef

__all__ = ["OffloadRef", "OffloadRefStore"]
