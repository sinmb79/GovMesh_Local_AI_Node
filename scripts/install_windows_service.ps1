param(
  [string]$ControlPlaneUrl = "http://127.0.0.1:8787",
  [string]$NodeId = "",
  [string]$TaskName = "GovMeshNodeAgent",
  [switch]$ServiceMode
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if ([string]::IsNullOrWhiteSpace($NodeId)) {
  throw "NodeId is required. Register the node first, then install the worker."
}

$Python = (Get-Command python).Source
$WorkerArgs = "-m apps.node_agent run-worker --control-plane `"$ControlPlaneUrl`" --node-id `"$NodeId`" --interval 5"

if ($ServiceMode) {
  $IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
  if (-not $IsAdmin) {
    throw "ServiceMode requires an elevated PowerShell session. Run without -ServiceMode for current-user scheduled task mode."
  }
  sc.exe create GovMeshNodeAgent binPath= "`"$Python`" $WorkerArgs" start= delayed-auto DisplayName= "GovMesh Node Agent" | Out-Host
  Write-Host "Windows service created: GovMeshNodeAgent"
} else {
  $Action = New-ScheduledTaskAction -Execute $Python -Argument $WorkerArgs -WorkingDirectory $Root
  $Trigger = New-ScheduledTaskTrigger -AtLogOn
  $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "GovMesh Node Agent worker" -Force | Out-Null
  Write-Host "Scheduled task created: $TaskName"
}
