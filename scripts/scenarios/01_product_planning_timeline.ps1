# 模拟一个用户围绕产品规划连续推进 Only-One-Memory 的真实对话时间线。
param(
    [string]$BaseUrl = $(if ($env:OOM_BASE_URL) { $env:OOM_BASE_URL } else { "http://127.0.0.1:8710" }),
    [string]$TenantId = "debug-realistic",
    [string]$RunId = $(Get-Date -Format "yyyyMMddHHmmss")
)

$ErrorActionPreference = "Stop"

$UserId = "pm-luo"
$AgentId = "oom-agent"
$SessionId = "planning-$RunId"
$SessionKey = "$AgentId`:$UserId`:$SessionId"

function Invoke-OomPost {
    param([string]$Path, [hashtable]$Body)
    $json = $Body | ConvertTo-Json -Depth 20
    Invoke-RestMethod -Method Post -Uri "$BaseUrl$Path" -ContentType "application/json; charset=utf-8" -Body $json
}

function Send-Turn {
    param(
        [int]$TurnNo,
        [string]$At,
        [string]$UserText,
        [string]$AssistantText
    )
    $assistantAt = ([datetimeoffset]::Parse($At)).AddSeconds(35).ToString("o")
    $body = @{
        tenant_id = $TenantId
        user_id = $UserId
        agent_id = $AgentId
        session_id = $SessionId
        session_key = $SessionKey
        idempotency_key = "$RunId-product-planning-turn-$TurnNo"
        messages = @(
            @{ role = "user"; content = $UserText; timestamp = $At; metadata = @{ turn_no = $TurnNo; speaker_intent = "planning" } },
            @{ role = "assistant"; content = $AssistantText; timestamp = $assistantAt; metadata = @{ turn_no = $TurnNo; reply_style = "decision_notes" } }
        )
        metadata = @{ scenario = "product_planning_timeline"; run_id = $RunId }
    }
    $result = Invoke-OomPost -Path "/v1/capture/turn" -Body $body
    Write-Host "turn $TurnNo recorded: $($result.l0_recorded_count) events"
}

Send-Turn 1 "2026-05-20T09:00:00+08:00" `
    "我今天要把 Only-One-Memory 的定位讲清楚：它不是聊天记录库，而是 Agent 的长期记忆底座。帮我记住这个方向。" `
    "已记住：Only-One-Memory 的产品定位是 Agent 长期记忆底座，重点不是简单聊天记录归档。"

Send-Turn 2 "2026-05-20T09:18:00+08:00" `
    "第一阶段只做 L0/L1，L2/L3 可以先保留接口。我怕一开始就做太重，调试成本会爆炸。" `
    "建议把第一阶段目标收敛为：可靠采集 L0、生成最小 L1、支持搜索和 before recall。L2/L3 先通过契约占位。"

Send-Turn 3 "2026-05-20T10:05:00+08:00" `
    "用户侧配置要少，默认 SQLite 能跑，生产再切 Postgres。Postgres 主要用于远端调试和部署。" `
    "已记录偏好：默认配置尽量少，本地走 SQLite，远端/生产走 Postgres，避免让用户一上来填很多参数。"

Send-Turn 4 "2026-05-20T10:42:00+08:00" `
    "召回结果必须能解释来源。我不想要那种凭空冒出来的记忆，最好每条都能回到 source_event_ids。" `
    "这是核心约束：L1 记忆必须保留 source_event_ids，召回上下文要能下钻到 L0 证据。"

Send-Turn 5 "2026-05-20T11:30:00+08:00" `
    "给我形成一个今天上午的产品决策摘要，后面我问到路线图时要能召回这些约束。" `
    "上午决策摘要：产品定位是 Agent 长期记忆底座；第一阶段聚焦 L0/L1、搜索、recall；默认少配置；Postgres 用于远端/生产；召回必须可追溯。"

$recall = Invoke-OomPost -Path "/v1/recall/before" -Body @{
    tenant_id = $TenantId
    user_id = $UserId
    agent_id = $AgentId
    session_id = $SessionId
    session_key = $SessionKey
    user_text = "Only-One-Memory 第一阶段产品路线和约束是什么？"
    max_results = 8
}
Write-Host "recall dynamic_context length: $($recall.dynamic_context.Length)"
Write-Host "scenario done: tenant=$TenantId user=$UserId session=$SessionId run=$RunId"
