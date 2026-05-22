# 模拟工具调用产生大结果，再把摘要写入对话和 offload entry。
param(
    [string]$BaseUrl = $(if ($env:OOM_BASE_URL) { $env:OOM_BASE_URL } else { "http://127.0.0.1:8710" }),
    [string]$TenantId = "debug-realistic",
    [string]$RunId = $(Get-Date -Format "yyyyMMddHHmmss")
)

$ErrorActionPreference = "Stop"

$UserId = "ops-zhao"
$AgentId = "oom-agent"
$SessionId = "tool-offload-$RunId"
$SessionKey = "$AgentId`:$UserId`:$SessionId"

function Invoke-OomPost {
    param([string]$Path, [hashtable]$Body)
    $json = $Body | ConvertTo-Json -Depth 30
    Invoke-RestMethod -Method Post -Uri "$BaseUrl$Path" -ContentType "application/json; charset=utf-8" -Body $json
}

function Invoke-OomGet {
    param([string]$Path)
    Invoke-RestMethod -Method Get -Uri "$BaseUrl$Path"
}

function Send-Turn {
    param([int]$TurnNo, [string]$At, [string]$UserText, [string]$AssistantText, [array]$ToolEvents = @())
    $assistantAt = ([datetimeoffset]::Parse($At)).AddSeconds(40).ToString("o")
    $result = Invoke-OomPost -Path "/v1/capture/turn" -Body @{
        tenant_id = $TenantId
        user_id = $UserId
        agent_id = $AgentId
        session_id = $SessionId
        session_key = $SessionKey
        idempotency_key = "$RunId-tool-offload-turn-$TurnNo"
        messages = @(
            @{ role = "user"; content = $UserText; timestamp = $At; metadata = @{ turn_no = $TurnNo } },
            @{ role = "assistant"; content = $AssistantText; timestamp = $assistantAt; metadata = @{ turn_no = $TurnNo } }
        )
        tool_events = $ToolEvents
        metadata = @{ scenario = "tool_offload_timeline"; run_id = $RunId }
    }
    Write-Host "turn $TurnNo recorded: $($result.l0_recorded_count) events"
}

$rawLog = @"
2026-05-20 19:00:01 INFO service started
2026-05-20 19:00:03 INFO postgres connected remote=true
2026-05-20 19:00:05 WARN recall latency p95=830ms
2026-05-20 19:00:08 INFO capture turn count=42
2026-05-20 19:00:11 ERROR offload restore missed ref_id=debug-missing-ref
2026-05-20 19:00:13 INFO retry restore succeeded ref_id=debug-restored-ref
"@

Send-Turn 1 "2026-05-20T19:00:00+08:00" `
    "我贴一段服务日志，你帮我判断 Postgres 远端调试有没有明显异常。" `
    "我会先检查连接、写入、召回延迟和 offload restore 相关日志，再给出摘要。"

$ref = Invoke-OomPost -Path "/v1/offload/refs" -Body @{
    tenant_id = $TenantId
    user_id = $UserId
    agent_id = $AgentId
    session_id = $SessionId
    kind = "tool_result"
    content = $rawLog
    metadata = @{ scenario = "tool_offload_timeline"; run_id = $RunId; tool = "read_service_log" }
}
Write-Host "offload ref created: $($ref.id)"

$entry = Invoke-OomPost -Path "/v1/offload/entries" -Body @{
    tenant_id = $TenantId
    user_id = $UserId
    agent_id = $AgentId
    session_id = $SessionId
    tool_call_id = "read-log-$RunId"
    tool_name = "read_service_log"
    summary = "服务已连接远端 Postgres；写入正常；recall p95 约 830ms；曾出现一次 missing ref 后重试成功。"
    score = 9
    node_id = "LOG1"
    result_ref = $ref.id
    metadata = @{ scenario = "tool_offload_timeline"; run_id = $RunId }
}
Write-Host "offload entry created: $($entry.node_id)"

Send-Turn 2 "2026-05-20T19:08:00+08:00" `
    "你读完日志了吗？不要把完整日志塞进上下文，只告诉我摘要和风险。" `
    "摘要：远端 Postgres 已连接且 capture 正常；风险是 recall p95 约 830ms 偏高，以及 offload restore 曾有 missing ref。完整日志已通过 offload ref 保存。" `
    @(@{ name = "read_service_log"; arguments = @{ path = "remote-service.log" }; result = @{ summary = $entry.summary; result_ref = $ref.id }; timestamp = "2026-05-20T19:07:30+08:00" })

Send-Turn 3 "2026-05-20T19:20:00+08:00" `
    "后面如果我问 LOG1，你要能恢复原始日志。" `
    "已记录：LOG1 对应本次服务日志的 offload entry，可通过 node_id 或 result_ref 恢复原文。"

$restored = Invoke-OomPost -Path "/v1/offload/restore" -Body @{
    tenant_id = $TenantId
    session_id = $SessionId
    node_id = "LOG1"
}
Write-Host "restored raw length: $($restored.raw_content.Length)"

$graph = Invoke-OomGet -Path "/v1/offload/graph/$SessionId`?tenant_id=$TenantId"
Write-Host "graph length: $($graph.mermaid.Length)"
Write-Host "scenario done: tenant=$TenantId user=$UserId session=$SessionId run=$RunId ref=$($ref.id)"
