from fastapi import FastAPI

from oom.app.api import admin, capture, health, offload, profiles, recall, scenes, search
from oom.memory_core.config import AppConfig


def create_app() -> FastAPI:
    config = AppConfig()
    app = FastAPI(title="Only One Memory")
    app.state.config = config
    app.include_router(health.router, prefix="/v1")
    app.include_router(capture.router, prefix="/v1")
    app.include_router(search.router, prefix="/v1")
    app.include_router(recall.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")
    app.include_router(scenes.router, prefix="/v1")
    app.include_router(profiles.router, prefix="/v1")
    app.include_router(offload.router, prefix="/v1")
    return app
