from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app
from oom.memory_core.admin.export_import import MemoryExport
from oom.memory_core.pipeline.checkpoint import PipelineSessionState
from oom.memory_core.types import CaptureTurnRequest, ConversationMessage


def test_memory_export_version_is_explicit():
    export = MemoryExport(version=1, tenant_id="default", records={})

    assert export.version == 1
    assert export.tenant_id == "default"


async def test_admin_export_contains_core_record_buckets(monkeypatch):
    monkeypatch.delenv("OOM_API_KEY", raising=False)
    monkeypatch.delenv("ONLY_ONE_MEMORY_API_KEY", raising=False)
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        capture = CaptureTurnRequest(
            tenant_id="default",
            user_id="u1",
            agent_id="a1",
            session_id="s1",
            session_key="a1:u1:s1",
            idempotency_key="export-1",
            messages=[
                ConversationMessage(
                    role="user",
                    content="需要导出这段记忆",
                    timestamp=datetime(2026, 5, 19, tzinfo=timezone.utc),
                )
            ],
        )
        await client.post("/v1/capture/turn", json=capture.model_dump(mode="json"))
        response = await client.post("/v1/admin/export", json={"tenant_id": "default"})

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["tenant_id"] == "default"
    assert set(body["records"]) >= {"l0", "l1", "l2", "l3", "offload_refs", "pipeline_state", "audit"}
    assert len(body["records"]["l0"]) == 1


async def test_admin_import_returns_layer_counts(monkeypatch):
    monkeypatch.delenv("OOM_API_KEY", raising=False)
    monkeypatch.delenv("ONLY_ONE_MEMORY_API_KEY", raising=False)
    app = create_app()
    payload = MemoryExport(
        version=1,
        tenant_id="default",
        records={
            "l0": [],
            "l1": [],
            "l2": [],
            "l3": [],
            "offload_entries": [],
            "audit": [],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/admin/import", json=payload.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.json()["imported"]["l0"] == 0


async def test_admin_import_restores_offload_refs_and_pipeline_state(tmp_path, monkeypatch):
    monkeypatch.delenv("OOM_API_KEY", raising=False)
    monkeypatch.delenv("ONLY_ONE_MEMORY_API_KEY", raising=False)
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "source.db"))
    monkeypatch.setenv("OOM_DATA_DIR", str(tmp_path / "source-offload"))
    source = create_app()
    async with AsyncClient(transport=ASGITransport(app=source), base_url="http://test") as client:
        ref = await client.post(
            "/v1/offload/refs",
            json={
                "tenant_id": "default",
                "user_id": "u1",
                "agent_id": "a1",
                "session_id": "s1",
                "kind": "tool_result",
                "content": "restorable raw",
                "metadata": {},
            },
        )
        core = source.state.memory_core if hasattr(source.state, "memory_core") else None
        if core is None:
            await client.get("/v1/admin/pipeline/status")
            core = source.state.memory_core
        core.pipeline.load_states({"s1": PipelineSessionState.new("s1", enable_warmup=True)})
        exported = await client.post("/v1/admin/export", json={"tenant_id": "default"})

    await source.state.memory_core.close()

    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "target.db"))
    monkeypatch.setenv("OOM_DATA_DIR", str(tmp_path / "target-offload"))
    target = create_app()
    async with AsyncClient(transport=ASGITransport(app=target), base_url="http://test") as client:
        imported = await client.post("/v1/admin/import", json=exported.json())
        restored = await client.post(
            "/v1/offload/restore",
            json={"tenant_id": "default", "session_id": "s1", "result_ref": ref.json()["id"]},
        )
        status = await client.get("/v1/admin/pipeline/status")

    await target.state.memory_core.close()

    assert imported.status_code == 200
    assert imported.json()["imported"]["offload_refs"] == 1
    assert imported.json()["imported"]["pipeline_state"] == 1
    assert restored.json()["raw_content"] == "restorable raw"
    assert status.json()["l1"]["sessions"] == 1
