$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$EnvScript = Join-Path $Root ".govmesh-local\env.ps1"

Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python 3.11 이상이 필요합니다. Python 설치 후 PowerShell을 다시 열어주세요."
}

if (-not (Test-Path $Python)) {
  python -m venv $Venv
  if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
}

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
& $Python -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw "Failed to install GovMesh package." }
& $Python scripts/setup_local_env.py
if ($LASTEXITCODE -ne 0) { throw "Failed to create local environment files." }
. $EnvScript
& $Python scripts/govmesh_doctor.py --ports=""
if ($LASTEXITCODE -ne 0) { throw "GovMesh readiness check failed." }

Write-Host ""
Write-Host "GovMesh 설치가 완료되었습니다."
Write-Host "다음 명령으로 환경 변수를 불러오세요:"
Write-Host ". .\.govmesh-local\env.ps1"
