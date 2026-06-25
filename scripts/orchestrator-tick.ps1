# One unattended orchestrator tick: lock -> headless cycle -> release -> log.
# Registered to run every 15 min by install-orchestrator.ps1.
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

# Acquire the tick lock; skip cleanly if a previous cycle is still running.
& $py -m bookieskit.orchestration lock acquire --path $lock | Out-Null
if ($LASTEXITCODE -ne 0) { Log "busy — previous cycle still running; skipping tick"; exit 0 }

try {
    Log "tick start"
    # Headless one cycle under the constrained permission profile.
    & claude -p "/orchestrate" --settings (Join-Path $repo ".claude\orchestrator-settings.json") 2>&1 | Add-Content -Encoding utf8 $log
    $claudeExit = $LASTEXITCODE  # capture claude's native exit immediately (defensive — before any later command)
    Log "tick done (claude exit $claudeExit)"
}
finally {
    & $py -m bookieskit.orchestration lock release --path $lock | Out-Null
    Log "lock released"
}
