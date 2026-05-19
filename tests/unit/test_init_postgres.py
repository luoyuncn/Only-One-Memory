import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

from scripts.init_postgres import (
    build_admin_dsn,
    create_database_if_missing,
    ensure_vector_extension,
    quote_identifier,
    target_database_name,
)


def test_target_database_name_reads_oom_from_dsn():
    dsn = "postgresql+asyncpg://user:pass@example.com:5432/oom"

    assert target_database_name(dsn) == "oom"


def test_build_admin_dsn_uses_postgres_database_and_preserves_query():
    dsn = "postgresql+asyncpg://user:pass@example.com:5432/oom?ssl=require"

    assert build_admin_dsn(dsn) == "postgresql://user:pass@example.com:5432/postgres?ssl=require"


def test_quote_identifier_escapes_double_quotes():
    assert quote_identifier('oom"test') == '"oom""test"'


def test_script_entrypoint_can_import_project_package(tmp_path):
    script = Path(__file__).parents[2] / "scripts" / "init_postgres.py"
    env = os.environ.copy()
    env.pop("OOM_POSTGRES_DSN", None)
    env.pop("ONLY_ONE_MEMORY_POSTGRES_DSN", None)

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "ModuleNotFoundError" not in output
    assert "OOM_POSTGRES_DSN is required" in output


async def test_create_database_reports_insufficient_privilege(monkeypatch):
    class FakeConnection:
        async def fetchval(self, query: str, database: str):
            return None

        async def execute(self, query: str):
            raise asyncpg.exceptions.InsufficientPrivilegeError("permission denied to create database")

        async def close(self):
            return None

    async def fake_connect(*, dsn: str):
        return FakeConnection()

    monkeypatch.setattr("scripts.init_postgres.asyncpg.connect", fake_connect)

    with pytest.raises(PermissionError, match="cannot create database"):
        await create_database_if_missing("postgresql+asyncpg://user:pass@example.com:5432/oom")


async def test_ensure_vector_extension_runs_on_target_database(monkeypatch):
    calls = []

    class FakeConnection:
        async def execute(self, query: str):
            calls.append(query)

        async def close(self):
            calls.append("close")

    async def fake_connect(*, dsn: str):
        calls.append(dsn)
        return FakeConnection()

    monkeypatch.setattr("scripts.init_postgres.asyncpg.connect", fake_connect)

    await ensure_vector_extension("postgresql+asyncpg://user:pass@example.com:5432/oom")

    assert calls == [
        "postgresql://user:pass@example.com:5432/oom",
        "CREATE EXTENSION IF NOT EXISTS vector",
        "close",
    ]


async def test_ensure_vector_extension_reports_missing_pgvector(monkeypatch):
    class FakeConnection:
        async def execute(self, query: str):
            raise asyncpg.exceptions.FeatureNotSupportedError('extension "vector" is not available')

        async def close(self):
            return None

    async def fake_connect(*, dsn: str):
        return FakeConnection()

    monkeypatch.setattr("scripts.init_postgres.asyncpg.connect", fake_connect)

    with pytest.raises(RuntimeError, match="pgvector extension is not available"):
        await ensure_vector_extension("postgresql+asyncpg://user:pass@example.com:5432/oom")
