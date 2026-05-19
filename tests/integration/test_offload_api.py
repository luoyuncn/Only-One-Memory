from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app


async def test_offload_ref_restore_api(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_DATA_DIR", str(tmp_path))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/v1/offload/refs",
            json={
                "tenant_id": "default",
                "user_id": "u1",
                "agent_id": "a1",
                "session_id": "s1",
                "kind": "tool_result",
                "content": "raw result",
                "metadata": {},
            },
        )
        restored = await client.post(
            "/v1/offload/restore",
            json={
                "tenant_id": "default",
                "session_id": "s1",
                "result_ref": created.json()["id"],
            },
        )

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert restored.status_code == 200
    assert restored.json()["raw_content"] == "raw result"


async def test_offload_restore_rejects_cross_tenant_ref(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_DATA_DIR", str(tmp_path))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/v1/offload/refs",
            json={
                "tenant_id": "tenant-a",
                "user_id": "u1",
                "agent_id": "a1",
                "session_id": "s1",
                "kind": "tool_result",
                "content": "secret raw result",
                "metadata": {},
            },
        )
        restored = await client.post(
            "/v1/offload/restore",
            json={
                "tenant_id": "tenant-b",
                "session_id": "s1",
                "result_ref": created.json()["id"],
            },
        )
        fetched = await client.get(
            f"/v1/offload/refs/{created.json()['id']}?tenant_id=tenant-b&session_id=s1"
        )

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert restored.status_code == 404
    assert fetched.status_code == 404
