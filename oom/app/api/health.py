"""健康检查 API，用于容器和集成测试确认服务存活。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "oom"}
