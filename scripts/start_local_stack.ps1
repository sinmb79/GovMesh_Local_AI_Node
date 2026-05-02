$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$EnvScript = Join-Path $Root ".govmesh-local\env.ps1"
$RunDir = Join-Path $Root ".govmesh-local"
$LogDir = Join-Path $RunDir "logs"
$PidFile = Join-Path $RunDir "govmesh-pids.json"

Set-Location $Root

if (Test-Path $EnvScript) {
  . $EnvScript
} else {
  & $Python scripts/setup_local_env.py | Out-Null
  . $EnvScript
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$services = @(
  @{ Name = "control-plane"; Args = @("-m", "apps.control_plane"); Out = "control-plane.out.log"; Err = "control-plane.err.log" },
  @{ Name = "quarantine-gateway"; Args = @("-m", "apps.quarantine_gateway"); Out = "quarantine-gateway.out.log"; Err = "quarantine-gateway.err.log" },
  @{ Name = "admin-ui"; Args = @("-m", "apps.admin_ui", "--control-plane", "http://127.0.0.1:8787", "--serve"); Out = "admin-ui.out.log"; Err = "admin-ui.err.log" }
)

$started = @()
foreach ($service in $services) {
  $process = Start-Process -FilePath $Python `
    -ArgumentList $service.Args `
    -WorkingDirectory $Root `
    -RedirectStandardOutput (Join-Path $LogDir $service.Out) `
    -RedirectStandardError (Join-Path $LogDir $service.Err) `
    -WindowStyle Hidden `
    -PassThru
  $started += [pscustomobject]@{ name = $service.Name; pid = $process.Id }
}

$started | ConvertTo-Json | Set-Content -Path $PidFile -Encoding UTF8
Write-Host "GovMesh local stack started."
Write-Host "Admin UI: http://127.0.0.1:8795"
Write-Host "PID file: $PidFile"
