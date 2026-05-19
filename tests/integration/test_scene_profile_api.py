from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app


async def test_list_scenes_empty_on_cold_start(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/scenes?tenant_id=default&user_id=u1")

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_patch_and_get_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        patch = await client.patch(
            "/v1/profiles/user/u1",
            json={"tenant_id": "default", "content": "# 用户画像\n用户重视证据。", "metadata": {}},
        )
        get = await client.get("/v1/profiles/user/u1?tenant_id=default")

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert patch.status_code == 200
    assert get.status_code == 200
    assert "证据" in get.json()["content"]


async def test_patch_and_get_scene(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        patch = await client.patch(
            "/v1/scenes/agent-memory",
            json={
                "tenant_id": "default",
                "user_id": "u1",
                "content": "## 用户核心特征\n用户重视证据。",
                "summary": "用户重视证据。",
                "heat": 2,
                "metadata": {},
            },
        )
        get = await client.get("/v1/scenes/agent-memory?tenant_id=default")

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert patch.status_code == 200
    assert get.status_code == 200
    assert get.json()["summary"] == "用户重视证据。"
