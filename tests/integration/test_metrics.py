from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app


async def test_metrics_endpoint_exposes_prometheus_text():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "oom_capture_total" in response.text
