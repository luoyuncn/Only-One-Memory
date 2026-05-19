# Only-One-Memory 运维手册

## 服务组成

生产部署建议至少包含：

- API 服务：运行 `oom.app.main:create_app`。
- Postgres：主存储后端。
- pgvector：为 Postgres 提供向量索引能力。
- 持久化目录：保存 offload refs 原始结果文件。

## 必要环境变量

推荐生产环境显式设置：

```bash
OOM_STORE_BACKEND=postgres
OOM_POSTGRES_DSN=postgresql://oom:oom@postgres:5432/oom
OOM_DATA_DIR=/data/offload
ONLY_ONE_MEMORY_API_KEY=change-me
```

`ONLY_ONE_MEMORY_API_KEY` 设置后，admin API 需要 `Authorization: Bearer <key>`。本地开发不设置该变量时，admin API 保持开放。

## Docker 启动

```bash
docker compose -f docker/docker-compose.yml up --build
```

启动后检查：

```bash
curl http://localhost:8710/v1/health
curl http://localhost:8710/v1/metrics
curl -H "Authorization: Bearer change-me" http://localhost:8710/v1/admin/pipeline/status
```

## 迁移与初始化

当前 store 在启动时会创建缺失表和索引。使用 Postgres 前先确认 pgvector 扩展可用：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

如果使用脚本初始化数据库：

```bash
uv run python scripts/init_postgres.py
```

生产 schema 迁移通过 Alembic baseline 管理：

```bash
uv run alembic upgrade head
```

## 备份

Postgres 备份：

```bash
pg_dump "$OOM_POSTGRES_DSN" > oom.sql
```

offload refs 备份：

```bash
tar -czf offload.tar.gz "$OOM_DATA_DIR"
```

建议同时保存 `docs/operations.md` 中记录的镜像版本、环境变量和部署时间。

## 恢复

先恢复 Postgres，再恢复 offload refs 目录：

```bash
psql "$OOM_POSTGRES_DSN" < oom.sql
mkdir -p "$OOM_DATA_DIR"
tar -xzf offload.tar.gz -C "$OOM_DATA_DIR"
```

恢复后执行：

```bash
curl -X POST -H "Authorization: Bearer $ONLY_ONE_MEMORY_API_KEY" http://localhost:8710/v1/admin/reindex
```

## 监控

`/v1/metrics` 暴露 Prometheus 文本格式，当前包含 capture、search、recall、pipeline、L1/L2/L3 与 offload restore 计数。

建议告警：

- API 健康检查连续失败。
- Postgres 连接失败。
- `/v1/metrics` 无法采集。
- offload refs 目录剩余空间不足。

## 故障处理

- admin API 返回 401：检查 `ONLY_ONE_MEMORY_API_KEY` 与 Authorization header。
- 搜索无结果：先调用 `/v1/admin/reindex` 重建 FTS 索引。
- Postgres 启动失败：确认 pgvector 镜像与数据目录权限。
- restore 返回 404：确认 offload refs 目录和数据库中的 `result_ref` 是否一致。
