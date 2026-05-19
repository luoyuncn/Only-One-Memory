from __future__ import annotations

from datetime import datetime

import pytest

from oom.memory_core.offload.ref_store import OffloadRefStore


def test_create_ref_persists_content_and_get_ref_restores_it(tmp_path):
    store = OffloadRefStore(tmp_path)

    ref = store.create_ref(
        tenant_id="default",
        user_id="u1",
        agent_id="a1",
        session_id="s1",
        kind="summary",
        content="这是一段被卸载的上下文内容",
        metadata={"source": "integration-test"},
    )

    restored = store.get_ref(ref.id)

    assert restored is not None
    assert restored.id == ref.id
    assert restored.tenant_id == "default"
    assert restored.user_id == "u1"
    assert restored.agent_id == "a1"
    assert restored.session_id == "s1"
    assert restored.kind == "summary"
    assert restored.content == "这是一段被卸载的上下文内容"
    assert restored.content_hash == ref.content_hash
    assert restored.metadata == {"source": "integration-test"}
    assert isinstance(restored.created_at, datetime)


@pytest.mark.parametrize("ref_id", ["../escape", "..\\escape", "nested/escape", "nested\\escape"])
def test_get_ref_rejects_path_traversal_ids(tmp_path, ref_id):
    store = OffloadRefStore(tmp_path)

    with pytest.raises(ValueError):
        store.get_ref(ref_id)
