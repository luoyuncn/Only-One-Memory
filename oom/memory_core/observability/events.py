"""结构化事件输出 helper，方便日志管道按事件类型收集运行轨迹。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def structured_event(name: str, **fields: Any) -> dict[str, Any]:
    return {
        "event": name,
        "ts": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
