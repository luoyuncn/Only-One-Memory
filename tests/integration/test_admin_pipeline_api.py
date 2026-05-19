from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app


async def test_pipeline_status_endpoint_returns_queue_state():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/admin/pipeline/status")

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert response.status_code == 200
    assert "l1" in response.json()


async def test_reindex_endpoint_returns_layer_counts(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/v1/capture/turn",
            json={
                "tenant_id": "default",
                "user_id": "u1",
                "agent_id": "a1",
                "session_id": "s1",
                "session_key": "agent:u1:s1",
                "idempotency_key": "turn-reindex",
                "messages": [{"role": "user", "content": "reindex me", "timestamp": "2026-05-19T00:00:00Z"}],
            },
        )
        response = await client.post("/v1/admin/reindex")

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert response.status_code == 200
    assert response.json()["l0"] == 1
