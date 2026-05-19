from oom.memory_core.config import AppConfig


def test_default_config_uses_sqlite_vec():
    cfg = AppConfig()

    assert cfg.store.backend == "sqlite"
    assert cfg.store.sqlite.vector_backend == "sqlite_vec"
    assert cfg.server.port == 8710


def test_postgres_config_requires_dsn():
    cfg = AppConfig.model_validate({"store": {"backend": "postgres", "postgres": {"dsn": ""}}})

    assert cfg.store.backend == "postgres"
    assert cfg.store.postgres.dsn == ""


def test_config_reads_oom_environment_variables(monkeypatch):
    monkeypatch.setenv("OOM_SQLITE_PATH", "custom.db")

    cfg = AppConfig()

    assert cfg.store.sqlite.path == "custom.db"
