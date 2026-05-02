$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python 3.11 이상이 필요합니다. Python 설치 후 PowerShell을 다시 열어주세요."
}

if (-not (Test-Path $Python)) {
  python -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -e .
& $Python scripts/setup_local_env.py
& $Python scripts/govmesh_doctor.py --ports=""

Write-Host ""
Write-Host "GovMesh 설치가 완료되었습니다."
Write-Host "다음 명령으로 환경 변수를 불러오세요:"
Write-Host ". .\.govmesh-local\env.ps1"
