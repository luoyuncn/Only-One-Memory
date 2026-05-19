from oom.memory_core.config import AppConfig


def _clear_config_env(monkeypatch):
    names = [
        "OOM_STORE_BACKEND",
        "ONLY_ONE_MEMORY_STORE_BACKEND",
        "OOM_POSTGRES_DSN",
        "ONLY_ONE_MEMORY_POSTGRES_DSN",
        "OOM_SQLITE_PATH",
        "ONLY_ONE_MEMORY_SQLITE_PATH",
    ]
    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_default_config_uses_sqlite_vec(tmp_path, monkeypatch):
    _clear_config_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
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


def test_config_reads_project_env_file(tmp_path, monkeypatch):
    _clear_config_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "OOM_STORE_BACKEND=postgres\n"
        "OOM_POSTGRES_DSN=postgresql+asyncpg://user:password@localhost:5432/oom\n",
        encoding="utf-8",
    )

    cfg = AppConfig()

    assert cfg.store.backend == "postgres"
    assert cfg.store.postgres.dsn == "postgresql+asyncpg://user:password@localhost:5432/oom"


def test_environment_variables_override_project_env_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OOM_STORE_BACKEND", "sqlite")
    (tmp_path / ".env").write_text("OOM_STORE_BACKEND=postgres\n", encoding="utf-8")

    cfg = AppConfig()

    assert cfg.store.backend == "sqlite"
