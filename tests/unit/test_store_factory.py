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


def test_env_file_postgres_config_creates_postgres_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OOM_STORE_BACKEND", raising=False)
    monkeypatch.delenv("ONLY_ONE_MEMORY_STORE_BACKEND", raising=False)
    monkeypatch.delenv("OOM_POSTGRES_DSN", raising=False)
    monkeypatch.delenv("ONLY_ONE_MEMORY_POSTGRES_DSN", raising=False)
    (tmp_path / ".env").write_text(
        "OOM_STORE_BACKEND=postgres\n"
        "OOM_POSTGRES_DSN=postgresql+asyncpg://user:password@localhost:5432/oom\n",
        encoding="utf-8",
    )

    store = create_store(AppConfig().store)

    assert store.capabilities().backend == "postgres"


def test_postgres_backend_ignores_sqlite_path(monkeypatch):
    monkeypatch.setenv("OOM_STORE_BACKEND", "postgres")
    monkeypatch.setenv("OOM_POSTGRES_DSN", "postgresql+asyncpg://user:password@localhost:5432/oom")
    monkeypatch.setenv("OOM_SQLITE_PATH", "should-not-be-used.db")

    store = create_store(AppConfig().store)

    assert store.capabilities().backend == "postgres"
