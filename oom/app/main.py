from fastapi import FastAPI

from oom.app.api import capture, health, search


def create_app() -> FastAPI:
    app = FastAPI(title="Only One Memory")
    app.include_router(health.router, prefix="/v1")
    app.include_router(capture.router, prefix="/v1")
    app.include_router(search.router, prefix="/v1")
    return app
