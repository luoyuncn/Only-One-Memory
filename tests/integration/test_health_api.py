from httpx import ASGITransport, AsyncClient

from only_one_memory.app.main import create_app


async def test_health_returns_ok():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "only-one-memory"}
