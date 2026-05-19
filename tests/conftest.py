import os

import pytest

from oom.app.main import CREATED_APPS


@pytest.fixture(autouse=True)
def default_to_sqlite_when_test_env_is_unset(monkeypatch):
    if not os.getenv("OOM_STORE_BACKEND") and not os.getenv("ONLY_ONE_MEMORY_STORE_BACKEND"):
        monkeypatch.setenv("OOM_STORE_BACKEND", "sqlite")
    yield


@pytest.fixture(autouse=True)
async def close_created_apps():
    yield
    for app in list(CREATED_APPS):
        core = getattr(app.state, "memory_core", None)
        if core is not None:
            await core.close()
        CREATED_APPS.discard(app)
