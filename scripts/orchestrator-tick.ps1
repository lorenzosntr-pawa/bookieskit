# One unattended orchestrator tick: lock -> headless cycle -> release -> log.
# Registered to run every 1 min by install-orchestrator.ps1; the cheap gate
# decides whether to actually wake the agent (claude) this tick.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$lockDir = Join-Path $repo ".orchestrator"
$lock = Join-Path $lockDir "tick.lock"
$logDir = Join-Path $lockDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("tick-" + (Get-Date -Format "yyyyMMdd") + ".log")
function Log($m) { "$(Get-Date -Format o) $m" | Add-Content -Encoding utf8 $log }

# Cheap gate: only wake the agent when there's something to do.
$gateOut = & $py -m bookieskit.orchestration gate --json
$run = $false
try { $run = ([bool]((ConvertFrom-Json $gateOut).run)) } catch { $run = $true }  # parse fail -> run (fail open)
if (-not $run) { Log "gate: idle - skipping"; exit 0 }

& $py -m bookieskit.orchestration lock acquire --path $lock | Out-Null
if ($LASTEXITCODE -ne 0) { Log "busy - previous cycle still running; skipping tick"; exit 0 }
try {
    Log "tick start (gate: run)"
    & claude -p "/orchestrate" --settings (Join-Path $repo ".claude\orchestrator-settings.json") 2>&1 | Add-Content -Encoding utf8 $log
    $claudeExit = $LASTEXITCODE
    Log "tick done (claude exit $claudeExit)"
    # Advance the watermark to the newest #tickets ts the gate observed, so we
    # don't re-fire on already-processed messages.
    $newest = $null
    try { $newest = (ConvertFrom-Json $gateOut).newest_ts } catch { $newest = $null }
    if ($newest) { Set-Content -Encoding ascii (Join-Path $repo ".orchestrator\slack-watermark") $newest }
}
finally {
    & $py -m bookieskit.orchestration lock release --path $lock | Out-Null
    Log "lock released"
}
