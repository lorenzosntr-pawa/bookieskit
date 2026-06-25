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
# Refresh the live #status board (cheap; keeps it current every tick).
function Board { & $py -m bookieskit.orchestration status board | Out-Null }

# Cheap gate: only wake the agent when there's something to do.
$gateOut = & $py -m bookieskit.orchestration gate --json
$run = $false
try { $run = ([bool]((ConvertFrom-Json $gateOut).run)) } catch { $run = $true }  # parse fail -> run (fail open)
if (-not $run) { Log "gate: idle - skipping"; Board; exit 0 }

& $py -m bookieskit.orchestration lock acquire --path $lock | Out-Null
if ($LASTEXITCODE -ne 0) { Log "busy - previous cycle still running; skipping tick"; Board; exit 0 }
try {
    Log "tick start (gate: run)"
    # Mint/refresh the GitHub App installation token so the cycle's git/gh act
    # as the App (an identity the main ruleset bars from merging), not as the
    # owner. If the App is not provisioned yet, fall back to the ambient login.
    $appToken = & $py -m bookieskit.orchestration token 2>$null
    if ($LASTEXITCODE -eq 0 -and $appToken) {
        $appToken = $appToken.Trim()
        $env:GH_TOKEN = $appToken
        $env:GITHUB_TOKEN = $appToken
        $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:" + $appToken))
        & git config --local "http.https://github.com/.extraheader" ("AUTHORIZATION: basic " + $basic)
        Log "using GitHub App identity for this cycle"
    } else {
        Log "App token unavailable - falling back to ambient gh login"
    }
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
    # Drop the per-cycle App auth header so it never leaks into other git use.
    & git config --local --unset "http.https://github.com/.extraheader" 2>$null
    Log "lock released"
    Board
}
