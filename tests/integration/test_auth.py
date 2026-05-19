from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app


async def test_missing_api_key_is_rejected(monkeypatch):
    monkeypatch.setenv("ONLY_ONE_MEMORY_API_KEY", "secret")
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/admin/pipeline/status")

    assert response.status_code == 401


async def test_valid_api_key_allows_admin_access(monkeypatch):
    monkeypatch.setenv("ONLY_ONE_MEMORY_API_KEY", "secret")
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/admin/pipeline/status", headers={"Authorization": "Bearer secret"})

    assert response.status_code == 200


async def test_admin_access_stays_open_without_configured_key(monkeypatch):
    monkeypatch.delenv("OOM_API_KEY", raising=False)
    monkeypatch.delenv("ONLY_ONE_MEMORY_API_KEY", raising=False)
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/admin/pipeline/status")

    assert response.status_code == 200
