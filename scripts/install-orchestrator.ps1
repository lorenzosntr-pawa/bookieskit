# Register (or refresh) the every-1-minute orchestrator tick in Task Scheduler.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$tick = Join-Path $repo "scripts\orchestrator-tick.ps1"
$taskName = "BookieskitOrchestrator"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$tick`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "bookieskit agent company - 1-min orchestrate tick" `
    -Force
Write-Host "Registered task '$taskName' (every 1 min). Remove with: Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
