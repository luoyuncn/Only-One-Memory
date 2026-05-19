"""Reciprocal Rank Fusion 排序融合实现。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RrfHit:
    id: str
    score: float
    ranks: list[int]


def rrf_merge(rankings: list[list[str]], k: int = 60, limit: int | None = None) -> list[RrfHit]:
    scores: dict[str, float] = {}
    ranks: dict[str, list[int]] = {}
    for ranking in rankings:
        for index, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + index)
            ranks.setdefault(item_id, []).append(index)

    hits = [RrfHit(id=item_id, score=score, ranks=ranks[item_id]) for item_id, score in scores.items()]
    hits.sort(key=lambda hit: (-hit.score, min(hit.ranks), hit.id))
    return hits if limit is None else hits[:limit]
