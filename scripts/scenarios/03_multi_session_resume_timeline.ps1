# 模拟同一用户跨两个 session 工作，中途回来要求恢复上下文。
param(
    [string]$BaseUrl = $(if ($env:OOM_BASE_URL) { $env:OOM_BASE_URL } else { "http://127.0.0.1:8710" }),
    [string]$TenantId = "debug-realistic",
    [string]$RunId = $(Get-Date -Format "yyyyMMddHHmmss")
)

$ErrorActionPreference = "Stop"

$UserId = "engineer-wang"
$AgentId = "oom-agent"
$MorningSessionId = "pg-debug-morning-$RunId"
$AfternoonSessionId = "pg-debug-afternoon-$RunId"
$MorningSessionKey = "$AgentId`:$UserId`:$MorningSessionId"
$AfternoonSessionKey = "$AgentId`:$UserId`:$AfternoonSessionId"

function Invoke-OomPost {
    param([string]$Path, [hashtable]$Body)
    $json = $Body | ConvertTo-Json -Depth 20
    Invoke-RestMethod -Method Post -Uri "$BaseUrl$Path" -ContentType "application/json; charset=utf-8" -Body $json
}

function Send-Turn {
    param(
        [int]$TurnNo,
        [string]$SessionId,
        [string]$SessionKey,
        [string]$At,
        [string]$UserText,
        [string]$AssistantText
    )
    $assistantAt = ([datetimeoffset]::Parse($At)).AddSeconds(32).ToString("o")
    $result = Invoke-OomPost -Path "/v1/capture/turn" -Body @{
        tenant_id = $TenantId
        user_id = $UserId
        agent_id = $AgentId
        session_id = $SessionId
        session_key = $SessionKey
        idempotency_key = "$RunId-multi-session-$SessionId-turn-$TurnNo"
        messages = @(
            @{ role = "user"; content = $UserText; timestamp = $At; metadata = @{ turn_no = $TurnNo; phase = $SessionId } },
            @{ role = "assistant"; content = $AssistantText; timestamp = $assistantAt; metadata = @{ turn_no = $TurnNo; phase = $SessionId } }
        )
        metadata = @{ scenario = "multi_session_resume_timeline"; run_id = $RunId }
    }
    Write-Host "$SessionId turn $TurnNo recorded: $($result.l0_recorded_count) events"
}

Send-Turn 1 $MorningSessionId $MorningSessionKey "2026-05-20T09:30:00+08:00" `
    "我已经把服务连到远端 Postgres 了，数据也写进去了。下一步我要模拟真实 turn，而不是跑会清表的测试。" `
    "关键事实：当前服务已连接远端 Postgres 且已有数据；后续调试不能使用会清表的测试，应使用 HTTP 写入脚本。"

Send-Turn 2 $MorningSessionId $MorningSessionKey "2026-05-20T10:00:00+08:00" `
    "脚本要能单独执行，打到当前服务，不要直接连数据库。每个 turn 都要有 user 问了什么、assistant 回了什么。" `
    "已记录脚本约束：单独执行、通过 HTTP 调当前服务、不直连数据库、每轮包含 user 和 assistant 连贯内容。"

Send-Turn 3 $MorningSessionId $MorningSessionKey "2026-05-20T10:35:00+08:00" `
    "我想按照时间线写数据。比如上午做规划，下午纠正偏好，晚上做恢复和召回。" `
    "建议按真实日程建场景：规划、偏好纠正、跨 session 恢复、工具结果 offload、多租户隔离。"

Send-Turn 4 $AfternoonSessionId $AfternoonSessionKey "2026-05-20T15:00:00+08:00" `
    "我回来了。你根据上午的记忆告诉我，为什么不能直接跑 pytest 的 Postgres 测试？" `
    "因为现有 Postgres pytest 夹具可能清空表，远端已有真实数据时风险很高。此时应使用隔离 tenant 的 HTTP 场景脚本。"

Send-Turn 5 $AfternoonSessionId $AfternoonSessionKey "2026-05-20T15:25:00+08:00" `
    "那你继续记住：我现在要的是 5 个场景脚本，不是 Postman，也不是 pytest。" `
    "已记录最终需求：生成 5 个独立场景脚本，用 HTTP 向当前服务写入连续真实 turn。"

$recall = Invoke-OomPost -Path "/v1/recall/before" -Body @{
    tenant_id = $TenantId
    user_id = $UserId
    agent_id = $AgentId
    session_id = $AfternoonSessionId
    session_key = $AfternoonSessionKey
    user_text = "今天上午关于远端 Postgres 调试和脚本方式，我们定了什么约束？"
    max_results = 10
}
Write-Host "recall dynamic_context length: $($recall.dynamic_context.Length)"
Write-Host "scenario done: tenant=$TenantId user=$UserId morning=$MorningSessionId afternoon=$AfternoonSessionId run=$RunId"
