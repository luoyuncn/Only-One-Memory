from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app


async def test_capture_turn_then_search_conversation(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        capture = await client.post(
            "/v1/capture/turn",
            json={
                "tenant_id": "default",
                "user_id": "u1",
                "agent_id": "a1",
                "session_id": "s1",
                "session_key": "agent:u1:s1",
                "idempotency_key": "turn-1",
                "messages": [
                    {"role": "user", "content": "我正在做 Only-One-Memory", "timestamp": "2026-05-19T00:00:00Z"},
                    {"role": "assistant", "content": "我们先做 L0", "timestamp": "2026-05-19T00:00:01Z"},
                ],
            },
        )
        search = await client.post(
            "/v1/conversations/search",
            json={"tenant_id": "default", "user_id": "u1", "query": "Only-One-Memory", "limit": 5},
        )

    assert capture.status_code == 200
    assert capture.json()["l0_recorded_count"] == 2
    assert search.status_code == 200
    assert search.json()["total"] >= 1
