import pytest

from oom.app.main import CREATED_APPS


@pytest.fixture(autouse=True)
async def close_created_apps():
    yield
    for app in list(CREATED_APPS):
        core = getattr(app.state, "memory_core", None)
        if core is not None:
            await core.close()
        CREATED_APPS.discard(app)
