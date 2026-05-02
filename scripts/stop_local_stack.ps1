$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PidFile = Join-Path $Root ".govmesh-local\govmesh-pids.json"

if (-not (Test-Path $PidFile)) {
  Write-Host "PID file not found. Nothing to stop."
  exit 0
}

$items = Get-Content -Path $PidFile -Raw | ConvertFrom-Json
foreach ($item in $items) {
  $process = Get-Process -Id $item.pid -ErrorAction SilentlyContinue
  if ($process) {
    Stop-Process -Id $item.pid -Force
    Write-Host "Stopped $($item.name) ($($item.pid))"
  }
}

Remove-Item -LiteralPath $PidFile -Force
Write-Host "GovMesh local stack stopped."
