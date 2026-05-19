from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from oom.memory_core.types import CaptureResult


def request_hash(request: BaseModel) -> str:
    payload = request.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class IdempotencyCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[str, CaptureResult]] = {}

    def get(self, key: str, digest: str) -> CaptureResult | None:
        item = self._items.get(key)
        if item is None:
            return None
        cached_digest, result = item
        if cached_digest != digest:
            raise ValueError("idempotency key reused with a different request body")
        return result

    def put(self, key: str, digest: str, result: CaptureResult) -> None:
        self._items[key] = (digest, result)
