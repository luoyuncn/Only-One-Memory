from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field


def _sqlite_vector_backend() -> Literal["sqlite_vec", "blob_bruteforce"]:
    value = os.getenv("ONLY_ONE_MEMORY_SQLITE_VECTOR_BACKEND", "sqlite_vec")
    if value == "blob_bruteforce":
        return "blob_bruteforce"
    return "sqlite_vec"


def _store_backend() -> Literal["sqlite", "postgres"]:
    value = os.getenv("ONLY_ONE_MEMORY_STORE_BACKEND", "sqlite")
    if value == "postgres":
        return "postgres"
    return "sqlite"


class ServerConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("ONLY_ONE_MEMORY_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("ONLY_ONE_MEMORY_PORT", "8710")))


class SqliteConfig(BaseModel):
    path: str = Field(default_factory=lambda: os.getenv("ONLY_ONE_MEMORY_SQLITE_PATH", "only_one_memory.db"))
    vector_backend: Literal["sqlite_vec", "blob_bruteforce"] = Field(default_factory=_sqlite_vector_backend)
    vector_dimension: int = Field(default_factory=lambda: int(os.getenv("ONLY_ONE_MEMORY_VECTOR_DIMENSION", "1536")))


class PostgresConfig(BaseModel):
    dsn: str = Field(default_factory=lambda: os.getenv("ONLY_ONE_MEMORY_POSTGRES_DSN", ""))
    vector_dimension: int = Field(default_factory=lambda: int(os.getenv("ONLY_ONE_MEMORY_VECTOR_DIMENSION", "1536")))


class StoreConfig(BaseModel):
    backend: Literal["sqlite", "postgres"] = Field(default_factory=_store_backend)
    sqlite: SqliteConfig = Field(default_factory=SqliteConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)


class EmbeddingConfig(BaseModel):
    provider: Literal["none"] = "none"
    dimension: int = Field(default_factory=lambda: int(os.getenv("ONLY_ONE_MEMORY_VECTOR_DIMENSION", "1536")))


class RecallConfig(BaseModel):
    default_limit: int = 10
    max_limit: int = 50


class PipelineConfig(BaseModel):
    enable_l1: bool = False
    enable_l2: bool = False
    enable_l3: bool = False


class OffloadConfig(BaseModel):
    enabled: bool = False


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    recall: RecallConfig = Field(default_factory=RecallConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    offload: OffloadConfig = Field(default_factory=OffloadConfig)
