"""Embedding Runner 协议，隔离具体向量供应商。"""

from __future__ import annotations

from typing import Protocol


class EmbeddingService(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
