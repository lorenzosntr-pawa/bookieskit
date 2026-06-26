# Register (or refresh) the every-1-minute orchestrator tick in Task Scheduler.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$tick = Join-Path $repo "scripts\orchestrator-tick.ps1"
$taskName = "BookieskitOrchestrator"
# -WindowStyle Hidden + -NonInteractive so the 1-min tick does NOT pop a
# PowerShell console window every cycle (it ran on the owner's interactive
# desktop and the flashing window was maddening).
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -NonInteractive -ExecutionPolicy Bypass -File `"$tick`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)
# -Hidden hides the task entry in the scheduler UI; window-hiding is via the
# action args above.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -MultipleInstances IgnoreNew -Hidden
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "bookieskit agent company - 1-min orchestrate tick" `
    -Force
Write-Host "Registered task '$taskName' (every 1 min, hidden window)."
Write-Host "Remove with: Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
Write-Host ""
Write-Host "ZERO-window upgrade (recommended for an always-on/headless mini PC):"
Write-Host "run the tick in session 0 so no window can EVER appear AND it keeps"
Write-Host "running when you are logged off. Re-register with a logon principal"
Write-Host "(prompts for your Windows password once):"
Write-Host '  $p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Password -RunLevel Limited'
Write-Host '  Register-ScheduledTask -TaskName "BookieskitOrchestrator" -Action $action -Trigger $trigger -Settings $settings -Principal $p -Force'
Write-Host "(or in Task Scheduler: General tab -> 'Run whether user is logged on or not')."
