# Installs the calendar watcher on Windows as a scheduled task that starts at
# login, runs hidden inside WSL, and keeps going while you are logged in.
# Run from PowerShell (not inside WSL):
#   powershell -ExecutionPolicy Bypass -File install_watcher_windows.ps1
#   powershell -ExecutionPolicy Bypass -File install_watcher_windows.ps1 -Uninstall
# Options: -Distro <name from "wsl -l -v">   -RepoPath <path inside WSL>
param(
    [string]$Distro = "Ubuntu",
    [string]$RepoPath = "~/meeting-agent",
    [switch]$Uninstall
)

$TaskName = "MeetingAgentWatcher"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
wsl.exe -d $Distro -- pkill -f "run_watcher.sh"
wsl.exe -d $Distro -- pkill -f "meeting_agent watch"

if ($Uninstall) {
    Write-Host "Watcher removed."
    exit 0
}

# powershell -WindowStyle Hidden keeps the WSL console window out of sight.
$command = "wsl.exe -d $Distro -- sh -c '$RepoPath/infra/run_watcher.sh'"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -NoProfile -Command `"$command`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# No time limit (the default stops tasks after 3 days), and keep running on battery.
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Meeting Agent: joins Google Meet meetings the bot is invited to" | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "Watcher installed and started. It starts again every time you log in to Windows."
Write-Host "Log (inside WSL): $RepoPath/data/watcher.log"
