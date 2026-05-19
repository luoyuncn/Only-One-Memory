"""应用配置模型，从环境变量收敛存储、Pipeline、鉴权和 Offload 设置。"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field


def _env(name: str, legacy_name: str, default: str) -> str:
    """读取新旧环境变量名，兼容早期 ONLY_ONE_MEMORY_* 配置。"""
    return os.getenv(name) or os.getenv(legacy_name) or default


def _sqlite_vector_backend() -> Literal["sqlite_vec", "blob_bruteforce"]:
    value = _env("OOM_SQLITE_VECTOR_BACKEND", "ONLY_ONE_MEMORY_SQLITE_VECTOR_BACKEND", "sqlite_vec")
    if value == "blob_bruteforce":
        return "blob_bruteforce"
    return "sqlite_vec"


def _store_backend() -> Literal["sqlite", "postgres"]:
    value = _env("OOM_STORE_BACKEND", "ONLY_ONE_MEMORY_STORE_BACKEND", "sqlite")
    if value == "postgres":
        return "postgres"
    return "sqlite"


class ServerConfig(BaseModel):
    host: str = Field(default_factory=lambda: _env("OOM_HOST", "ONLY_ONE_MEMORY_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(_env("OOM_PORT", "ONLY_ONE_MEMORY_PORT", "8710")))


class SqliteConfig(BaseModel):
    path: str = Field(default_factory=lambda: _env("OOM_SQLITE_PATH", "ONLY_ONE_MEMORY_SQLITE_PATH", "oom.db"))
    vector_backend: Literal["sqlite_vec", "blob_bruteforce"] = Field(default_factory=_sqlite_vector_backend)
    vector_dimension: int = Field(default_factory=lambda: int(_env("OOM_VECTOR_DIMENSION", "ONLY_ONE_MEMORY_VECTOR_DIMENSION", "1536")))


class PostgresConfig(BaseModel):
    dsn: str = Field(default_factory=lambda: _env("OOM_POSTGRES_DSN", "ONLY_ONE_MEMORY_POSTGRES_DSN", ""))
    vector_dimension: int = Field(default_factory=lambda: int(_env("OOM_VECTOR_DIMENSION", "ONLY_ONE_MEMORY_VECTOR_DIMENSION", "1536")))


class StoreConfig(BaseModel):
    """Store 选择与各后端配置。"""

    backend: Literal["sqlite", "postgres"] = Field(default_factory=_store_backend)
    sqlite: SqliteConfig = Field(default_factory=SqliteConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)


class EmbeddingConfig(BaseModel):
    provider: Literal["none"] = "none"
    dimension: int = Field(default_factory=lambda: int(_env("OOM_VECTOR_DIMENSION", "ONLY_ONE_MEMORY_VECTOR_DIMENSION", "1536")))


class RecallConfig(BaseModel):
    default_limit: int = 10
    max_limit: int = 50


class PipelineConfig(BaseModel):
    """记忆管线配置，尽量用少量开关控制 L1/L2/L3 生命周期。"""

    enable_l1: bool = False
    enable_l2: bool = False
    enable_l3: bool = False
    enable_warmup: bool = True
    every_n_conversations: int = 5
    idle_timeout_seconds: int | None = 600
    checkpoint_path: str | None = Field(
        default_factory=lambda: os.getenv("OOM_PIPELINE_CHECKPOINT_PATH")
        or os.getenv("ONLY_ONE_MEMORY_PIPELINE_CHECKPOINT_PATH")
    )


class OffloadConfig(BaseModel):
    enabled: bool = False
    data_dir: str = Field(default_factory=lambda: _env("OOM_DATA_DIR", "ONLY_ONE_MEMORY_DATA_DIR", ".oom/offload"))


class SecurityConfig(BaseModel):
    api_key: str | None = Field(
        default_factory=lambda: os.getenv("OOM_API_KEY") or os.getenv("ONLY_ONE_MEMORY_API_KEY")
    )


class AppConfig(BaseModel):
    """应用总配置，FastAPI 和 worker 都从这里读取同一套运行参数。"""

    server: ServerConfig = Field(default_factory=ServerConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    recall: RecallConfig = Field(default_factory=RecallConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    offload: OffloadConfig = Field(default_factory=OffloadConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
