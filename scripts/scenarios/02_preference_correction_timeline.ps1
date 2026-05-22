# 模拟用户偏好被逐步澄清、纠正和覆盖的连续对话。
param(
    [string]$BaseUrl = $(if ($env:OOM_BASE_URL) { $env:OOM_BASE_URL } else { "http://127.0.0.1:8710" }),
    [string]$TenantId = "debug-realistic",
    [string]$RunId = $(Get-Date -Format "yyyyMMddHHmmss")
)

$ErrorActionPreference = "Stop"

$UserId = "designer-chen"
$AgentId = "oom-agent"
$SessionId = "preference-correction-$RunId"
$SessionKey = "$AgentId`:$UserId`:$SessionId"

function Invoke-OomPost {
    param([string]$Path, [hashtable]$Body)
    $json = $Body | ConvertTo-Json -Depth 20
    Invoke-RestMethod -Method Post -Uri "$BaseUrl$Path" -ContentType "application/json; charset=utf-8" -Body $json
}

function Send-Turn {
    param([int]$TurnNo, [string]$At, [string]$UserText, [string]$AssistantText)
    $assistantAt = ([datetimeoffset]::Parse($At)).AddSeconds(28).ToString("o")
    Invoke-OomPost -Path "/v1/capture/turn" -Body @{
        tenant_id = $TenantId
        user_id = $UserId
        agent_id = $AgentId
        session_id = $SessionId
        session_key = $SessionKey
        idempotency_key = "$RunId-preference-correction-turn-$TurnNo"
        messages = @(
            @{ role = "user"; content = $UserText; timestamp = $At; metadata = @{ turn_no = $TurnNo } },
            @{ role = "assistant"; content = $AssistantText; timestamp = $assistantAt; metadata = @{ turn_no = $TurnNo } }
        )
        metadata = @{ scenario = "preference_correction_timeline"; run_id = $RunId }
    } | Out-Null
    Write-Host "turn $TurnNo recorded"
}

Send-Turn 1 "2026-05-20T13:00:00+08:00" `
    "以后给我设计方案时，可以先写很多背景，我喜欢完整解释。" `
    "已记录：你当前偏好是设计方案里保留较完整的背景解释。"

Send-Turn 2 "2026-05-20T13:20:00+08:00" `
    "等一下，刚才那个偏好要修正。真正执行任务时不要长篇背景，先给结论和可执行步骤，背景放最后。" `
    "已修正：执行型回复优先给结论和步骤，背景信息后置。之前的长背景偏好只适用于研究型讨论。"

Send-Turn 3 "2026-05-20T14:05:00+08:00" `
    "我还希望你记住：涉及代码变更必须同步 AGENTS.md，env 变化才更新 .env.example。" `
    "已记录项目协作规则：代码变更同步 AGENTS.md；只有环境变量发生变化时同步 .env.example。"

Send-Turn 4 "2026-05-20T14:40:00+08:00" `
    "关于接口调试，我更想要脚本批量写真实对话，不想在 Postman 里一个个点。" `
    "已记录工具偏好：接口调试优先使用可重复执行的批量脚本生成真实对话流量，Postman 适合单点排查。"

Send-Turn 5 "2026-05-20T15:10:00+08:00" `
    "你现在总结一下我的偏好，注意不要把被我纠正掉的版本当作最终偏好。" `
    "最终偏好：执行型任务先给结论和步骤；代码变更同步 AGENTS.md；env 变化才改 .env.example；接口调试优先批量脚本。"

$recall = Invoke-OomPost -Path "/v1/recall/before" -Body @{
    tenant_id = $TenantId
    user_id = $UserId
    agent_id = $AgentId
    session_id = $SessionId
    session_key = $SessionKey
    user_text = "我现在对回复风格和接口调试方式的最终偏好是什么？"
    max_results = 10
}
Write-Host "recall dynamic_context length: $($recall.dynamic_context.Length)"
Write-Host "scenario done: tenant=$TenantId user=$UserId session=$SessionId run=$RunId"
