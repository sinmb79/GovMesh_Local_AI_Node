param(
  [string]$TaskName = "GovMeshNodeAgent",
  [switch]$ServiceMode
)

$ErrorActionPreference = "Stop"

if ($ServiceMode) {
  sc.exe stop GovMeshNodeAgent | Out-Null
  sc.exe delete GovMeshNodeAgent | Out-Host
  Write-Host "Windows service removed: GovMeshNodeAgent"
} else {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  Write-Host "Scheduled task removed: $TaskName"
}
