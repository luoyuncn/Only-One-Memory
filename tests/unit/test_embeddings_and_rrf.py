from oom.memory_core.embeddings.noop import NoopEmbeddingService
from oom.memory_core.recall.rrf import rrf_merge


async def test_noop_embedding_is_deterministic():
    service = NoopEmbeddingService(dimensions=4)

    assert await service.embed("abc") == await service.embed("abc")


def test_rrf_merge_boosts_items_seen_twice():
    merged = rrf_merge([["a", "b"], ["b", "c"]])

    assert merged[0].id == "b"
