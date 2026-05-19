from fastapi import FastAPI

from only_one_memory.app.api import health


def create_app() -> FastAPI:
    app = FastAPI(title="Only One Memory")
    app.include_router(health.router, prefix="/v1")
    return app
