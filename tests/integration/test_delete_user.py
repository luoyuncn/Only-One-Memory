from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from oom.app.main import create_app
from oom.memory_core.admin.delete_user import DeleteUserPlan
from oom.memory_core.types import CaptureTurnRequest, ConversationMessage


def test_delete_user_plan_lists_all_layers():
    plan = DeleteUserPlan.for_user(tenant_id="default", user_id="u1")

    assert plan.layers == ["l0", "l1", "l2", "l3", "offload", "indexes", "audit"]


async def test_admin_delete_user_removes_l0_records(tmp_path, monkeypatch):
    monkeypatch.setenv("OOM_SQLITE_PATH", str(tmp_path / "memory.db"))
    monkeypatch.delenv("OOM_API_KEY", raising=False)
    monkeypatch.delenv("ONLY_ONE_MEMORY_API_KEY", raising=False)
    app = create_app()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            capture = CaptureTurnRequest(
                tenant_id="default",
                user_id="u1",
                agent_id="a1",
                session_id="s1",
                session_key="a1:u1:s1",
                idempotency_key="delete-1",
                messages=[
                    ConversationMessage(
                        role="user",
                        content="这条记录稍后会被删除",
                        timestamp=datetime(2026, 5, 19, tzinfo=timezone.utc),
                    )
                ],
            )
            await client.post("/v1/capture/turn", json=capture.model_dump(mode="json"))
            response = await client.post("/v1/admin/delete-user", json={"tenant_id": "default", "user_id": "u1"})
            search = await client.post(
                "/v1/conversations/search",
                json={"tenant_id": "default", "user_id": "u1", "query": "删除", "limit": 5},
            )
    finally:
        core = getattr(app.state, "memory_core", None)
        if core is not None:
            await core.close()

    assert response.status_code == 200
    assert response.json()["deleted"]["l0"] == 1
    assert search.json()["total"] == 0
