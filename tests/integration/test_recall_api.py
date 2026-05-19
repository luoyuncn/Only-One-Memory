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
