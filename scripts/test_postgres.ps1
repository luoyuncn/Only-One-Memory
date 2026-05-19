# 读取本地 .env，初始化 Postgres schema，并运行 Postgres 专项测试。
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$envFile = Join-Path $repoRoot ".env"
if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

if (-not $env:OOM_STORE_BACKEND) {
    $env:OOM_STORE_BACKEND = "postgres"
}

if ($env:OOM_STORE_BACKEND -ne "postgres") {
    throw "OOM_STORE_BACKEND must be postgres for this test entrypoint."
}

if (-not $env:OOM_POSTGRES_DSN) {
    throw "OOM_POSTGRES_DSN is required. Set it in .env or the current shell."
}

uv run python scripts/init_postgres.py
uv run pytest `
    tests/integration/test_postgres_l0_store.py `
    tests/integration/test_l1_store_contract.py::test_postgres_l1_store_contract `
    tests/integration/test_postgres_pipeline_jobs.py `
    -q
