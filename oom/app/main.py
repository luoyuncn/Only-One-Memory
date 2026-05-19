"""FastAPI 应用工厂，负责装配所有 HTTP 路由和指标端点。"""

from weakref import WeakSet

from fastapi import FastAPI, Response

from oom.app.api import admin, capture, health, offload, profiles, recall, scenes, search
from oom.memory_core.config import AppConfig
from oom.memory_core.observability.metrics import render_prometheus_text


CREATED_APPS: WeakSet[FastAPI] = WeakSet()


def create_app() -> FastAPI:
    config = AppConfig()
    app = FastAPI(title="Only One Memory")
    CREATED_APPS.add(app)
    app.state.config = config
    app.include_router(health.router, prefix="/v1")
    app.include_router(capture.router, prefix="/v1")
    app.include_router(search.router, prefix="/v1")
    app.include_router(recall.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")
    app.include_router(scenes.router, prefix="/v1")
    app.include_router(profiles.router, prefix="/v1")
    app.include_router(offload.router, prefix="/v1")

    @app.get("/v1/metrics")
    async def metrics() -> Response:
        return Response(content=render_prometheus_text(), media_type="text/plain; version=0.0.4")

    return app
