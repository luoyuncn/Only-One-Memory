from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app


async def test_offload_entry_graph_restore_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_DATA_DIR", str(tmp_path / "offload"))
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ref = await client.post(
            "/v1/offload/refs",
            json={
                "tenant_id": "default",
                "user_id": "u1",
                "agent_id": "a1",
                "session_id": "s1",
                "kind": "tool_result",
                "content": "raw",
                "metadata": {},
            },
        )
        await client.post(
            "/v1/offload/entries",
            json={
                "tenant_id": "default",
                "session_id": "s1",
                "tool_call_id": "call1",
                "tool_name": "read_file",
                "summary": "读取文件",
                "score": 8,
                "node_id": "N1",
                "result_ref": ref.json()["id"],
            },
        )
        graph = await client.get("/v1/offload/graph/s1?tenant_id=default")
        restored = await client.post(
            "/v1/offload/restore",
            json={"tenant_id": "default", "session_id": "s1", "node_id": "N1"},
        )

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert "N1" in graph.json()["mermaid"]
    assert restored.json()["raw_content"] == "raw"


async def test_create_offload_entry_rejects_ref_scope_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_DATA_DIR", str(tmp_path / "offload"))
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ref = await client.post(
            "/v1/offload/refs",
            json={
                "tenant_id": "tenant-a",
                "user_id": "u1",
                "agent_id": "a1",
                "session_id": "s1",
                "kind": "tool_result",
                "content": "raw",
                "metadata": {},
            },
        )
        response = await client.post(
            "/v1/offload/entries",
            json={
                "tenant_id": "tenant-b",
                "session_id": "s1",
                "tool_call_id": "call1",
                "tool_name": "read_file",
                "summary": "读取文件",
                "score": 8,
                "node_id": "N1",
                "result_ref": ref.json()["id"],
            },
        )

    core = getattr(app.state, "memory_core", None)
    if core is not None:
        await core.close()

    assert response.status_code == 404
