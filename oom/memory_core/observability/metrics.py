from __future__ import annotations

from collections import defaultdict
from threading import Lock


_COUNTERS: dict[str, float] = defaultdict(float)
_LOCK = Lock()

KNOWN_COUNTERS = (
    "oom_capture_total",
    "oom_recall_total",
    "oom_search_total",
    "oom_pipeline_jobs_total",
    "oom_l1_extraction_total",
    "oom_l2_scene_generation_total",
    "oom_l3_persona_generation_total",
    "oom_offload_restore_total",
)


def increment(name: str, amount: float = 1.0) -> None:
    with _LOCK:
        _COUNTERS[name] += amount


def render_prometheus_text() -> str:
    with _LOCK:
        snapshot = {name: _COUNTERS[name] for name in KNOWN_COUNTERS}
    lines: list[str] = []
    for name in KNOWN_COUNTERS:
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name} {snapshot[name]:g}")
    return "\n".join(lines) + "\n"
