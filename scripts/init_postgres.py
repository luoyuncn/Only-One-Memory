from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_env_file(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_asyncpg_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


def target_database_name(dsn: str) -> str:
    parts = urlsplit(normalize_asyncpg_dsn(dsn))
    database = parts.path.lstrip("/")
    if not database:
        raise ValueError("OOM_POSTGRES_DSN must include a target database name, for example /oom")
    return database


def build_admin_dsn(dsn: str, maintenance_db: str = "postgres") -> str:
    parts = urlsplit(normalize_asyncpg_dsn(dsn))
    return urlunsplit((parts.scheme, parts.netloc, f"/{maintenance_db}", parts.query, parts.fragment))


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


async def create_database_if_missing(dsn: str, admin_dsn: str | None = None) -> None:
    database = target_database_name(dsn)
    admin_dsn = admin_dsn or build_admin_dsn(dsn)
    conn = await asyncpg.connect(dsn=admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", database)
        if exists:
            print(f"Database already exists: {database}")
            return
        try:
            await conn.execute(f"CREATE DATABASE {quote_identifier(database)}")
        except asyncpg.exceptions.InsufficientPrivilegeError as exc:
            raise PermissionError(
                f"Current Postgres user cannot create database {database!r}. "
                "Grant CREATEDB, set OOM_POSTGRES_ADMIN_DSN to a privileged maintenance database DSN, "
                "or create the database manually before running this script again."
            ) from exc
        print(f"Created database: {database}")
    finally:
        await conn.close()


async def ensure_vector_extension(dsn: str) -> None:
    conn = await asyncpg.connect(dsn=normalize_asyncpg_dsn(dsn))
    try:
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except asyncpg.exceptions.FeatureNotSupportedError as exc:
            raise RuntimeError(
                "pgvector extension is not available on the target Postgres server. "
                "Install pgvector on the server or enable it in the cloud database console, "
                "then run this script again."
            ) from exc
        print("Ensured pgvector extension in target database")
    finally:
        await conn.close()


async def initialize_schema(dsn: str) -> None:
    from oom.memory_core.config import PostgresConfig
    from oom.memory_core.stores.postgres_store import PostgresMemoryStore

    await ensure_vector_extension(dsn)
    store = PostgresMemoryStore(PostgresConfig(dsn=dsn))
    await store.init()
    await store.close()
    print("Initialized V0.1 Postgres schema")


async def main() -> None:
    load_env_file()
    dsn = os.getenv("OOM_POSTGRES_DSN")
    if not dsn:
        raise SystemExit("OOM_POSTGRES_DSN is required. Copy .env.example to .env and fill in the remote DSN.")
    admin_dsn = os.getenv("OOM_POSTGRES_ADMIN_DSN")
    try:
        await create_database_if_missing(dsn, admin_dsn=admin_dsn)
        await initialize_schema(dsn)
    except (PermissionError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    asyncio.run(main())
