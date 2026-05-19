from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def structured_event(name: str, **fields: Any) -> dict[str, Any]:
    return {
        "event": name,
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
