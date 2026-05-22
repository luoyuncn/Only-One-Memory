# 模拟两个租户使用相似关键词和相同 session_key，验证真实写入时不会串记忆。
param(
    [string]$BaseUrl = $(if ($env:OOM_BASE_URL) { $env:OOM_BASE_URL } else { "http://127.0.0.1:8710" }),
    [string]$RunId = $(Get-Date -Format "yyyyMMddHHmmss")
)

$ErrorActionPreference = "Stop"

$AgentId = "oom-agent"
$SharedSessionId = "shared-debug-session-$RunId"
$SharedSessionKey = "shared-session-key"

function Invoke-OomPost {
    param([string]$Path, [hashtable]$Body)
    $json = $Body | ConvertTo-Json -Depth 20
    Invoke-RestMethod -Method Post -Uri "$BaseUrl$Path" -ContentType "application/json; charset=utf-8" -Body $json
}

function Send-Turn {
    param(
        [string]$TenantId,
        [string]$UserId,
        [int]$TurnNo,
        [string]$At,
        [string]$UserText,
        [string]$AssistantText
    )
    $assistantAt = ([datetimeoffset]::Parse($At)).AddSeconds(30).ToString("o")
    $result = Invoke-OomPost -Path "/v1/capture/turn" -Body @{
        tenant_id = $TenantId
        user_id = $UserId
        agent_id = $AgentId
        session_id = $SharedSessionId
        session_key = $SharedSessionKey
        idempotency_key = "$RunId-$TenantId-$UserId-turn-$TurnNo"
        messages = @(
            @{ role = "user"; content = $UserText; timestamp = $At; metadata = @{ turn_no = $TurnNo; isolation_case = $TenantId } },
            @{ role = "assistant"; content = $AssistantText; timestamp = $assistantAt; metadata = @{ turn_no = $TurnNo; isolation_case = $TenantId } }
        )
        metadata = @{ scenario = "multi_tenant_isolation_timeline"; run_id = $RunId }
    }
    Write-Host "$TenantId/$UserId turn $TurnNo recorded: $($result.l0_recorded_count) events"
}

$TenantA = "debug-tenant-alpha-$RunId"
$TenantB = "debug-tenant-beta-$RunId"

Send-Turn $TenantA "alice" 1 "2026-05-20T20:00:00+08:00" `
    "我们的项目代号叫 Alpha Lantern，Postgres 调试时必须保护客户 A 的记忆。" `
    "已记录租户 Alpha 的项目代号：Alpha Lantern；重点是保护客户 A 的记忆隔离。"

Send-Turn $TenantA "alice" 2 "2026-05-20T20:10:00+08:00" `
    "Alpha Lantern 的召回关键词是 amber memory，不要和别的租户混在一起。" `
    "已记录：Alpha Lantern 关联关键词 amber memory，必须只在 Alpha 租户内召回。"

Send-Turn $TenantB "bob" 1 "2026-05-20T20:00:00+08:00" `
    "我们的项目代号叫 Beta Harbor，Postgres 调试时必须保护客户 B 的记忆。" `
    "已记录租户 Beta 的项目代号：Beta Harbor；重点是保护客户 B 的记忆隔离。"

Send-Turn $TenantB "bob" 2 "2026-05-20T20:10:00+08:00" `
    "Beta Harbor 的召回关键词也是 memory，但专属词是 blue anchor。" `
    "已记录：Beta Harbor 关联关键词 blue anchor，不能混入 Alpha 租户。"

$alphaRecall = Invoke-OomPost -Path "/v1/recall/before" -Body @{
    tenant_id = $TenantA
    user_id = "alice"
    agent_id = $AgentId
    session_id = $SharedSessionId
    session_key = $SharedSessionKey
    user_text = "amber memory 对应哪个项目？"
    max_results = 8
}

$betaRecall = Invoke-OomPost -Path "/v1/recall/before" -Body @{
    tenant_id = $TenantB
    user_id = "bob"
    agent_id = $AgentId
    session_id = $SharedSessionId
    session_key = $SharedSessionKey
    user_text = "blue anchor 对应哪个项目？"
    max_results = 8
}

Write-Host "alpha recall length: $($alphaRecall.dynamic_context.Length)"
Write-Host "beta recall length: $($betaRecall.dynamic_context.Length)"
Write-Host "scenario done: tenantA=$TenantA tenantB=$TenantB shared_session_key=$SharedSessionKey run=$RunId"
