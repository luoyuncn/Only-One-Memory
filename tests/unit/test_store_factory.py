from oom.memory_core.config import AppConfig
from oom.memory_core.stores.factory import create_store


def test_create_sqlite_store_from_config():
    cfg = AppConfig()

    store = create_store(cfg.store)

    assert store.capabilities().fts_search is True
    assert store.capabilities().vector_search is True


def test_create_postgres_store_from_config():
    cfg = AppConfig.model_validate(
        {"store": {"backend": "postgres", "postgres": {"dsn": "postgresql+asyncpg://u:p@localhost/db"}}}
    )

    store = create_store(cfg.store)

    assert store.capabilities().fts_search is True
    assert store.capabilities().vector_search is True
