from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app


async def test_recall_returns_dynamic_context_after_memory_exists(tmp_path, monkeypatch):
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
                "idempotency_key": "turn-1",
                "messages": [
                    {
                        "role": "user",
                        "content": "我在开发 Only-One-Memory",
                        "timestamp": "2026-05-19T00:00:00Z",
                    }
                ],
            },
        )
        response = await client.post(
            "/v1/recall/before",
            json={
                "tenant_id": "default",
                "user_id": "u1",
                "agent_id": "a1",
                "session_id": "s1",
                "session_key": "agent:u1:s1",
                "user_text": "继续 Only-One-Memory",
                "max_results": 5,
            },
        )

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert response.status_code == 200
    assert "dynamic_context" in response.json()


async def test_capture_triggers_minimal_l1_memory_search(tmp_path, monkeypatch):
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
                "idempotency_key": "turn-l1",
                "messages": [
                    {
                        "role": "user",
                        "content": "我在开发 Only-One-Memory 的流水线闭环",
                        "timestamp": "2026-05-19T00:00:00Z",
                    }
                ],
            },
        )
        response = await client.post(
            "/v1/memories/search",
            json={"tenant_id": "default", "user_id": "u1", "query": "Only-One-Memory", "limit": 5},
        )

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_l1_pipeline_does_not_mix_same_session_key_across_tenants(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for tenant_id, content in [("tenant-a", "alpha-only-memory"), ("tenant-b", "beta-only-memory")]:
            await client.post(
                "/v1/capture/turn",
                json={
                    "tenant_id": tenant_id,
                    "user_id": "u1",
                    "agent_id": "a1",
                    "session_id": "s1",
                    "session_key": "shared-session",
                    "idempotency_key": f"{tenant_id}-turn",
                    "messages": [{"role": "user", "content": content, "timestamp": "2026-05-19T00:00:00Z"}],
                },
            )
        tenant_a = await client.post(
            "/v1/memories/search",
            json={"tenant_id": "tenant-a", "session_key": "shared-session", "query": "alpha-only-memory", "limit": 5},
        )
        tenant_b = await client.post(
            "/v1/memories/search",
            json={"tenant_id": "tenant-b", "session_key": "shared-session", "query": "beta-only-memory", "limit": 5},
        )

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert tenant_a.json()["total"] == 1
    assert tenant_a.json()["hits"][0]["memory"]["tenant_id"] == "tenant-a"
    assert tenant_b.json()["total"] == 1
    assert tenant_b.json()["hits"][0]["memory"]["tenant_id"] == "tenant-b"
