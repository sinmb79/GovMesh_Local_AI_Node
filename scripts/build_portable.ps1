$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Dist = Join-Path $Root "dist\govmesh-portable"

if (Test-Path $Dist) {
  Remove-Item -LiteralPath $Dist -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $Dist | Out-Null

$items = @(
  "README.md",
  "pyproject.toml",
  ".env.example",
  "apps",
  "configs",
  "packages",
  "docs",
  "samples",
  "scripts",
  "tests"
)

foreach ($item in $items) {
  $source = Join-Path $Root $item
  $target = Join-Path $Dist $item
  if (Test-Path $source) {
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
  }
}

Get-ChildItem -Path $Dist -Recurse -Force -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path $Dist -Recurse -Force -Directory -Filter ".pytest_cache" | Remove-Item -Recurse -Force

Write-Host "Portable bundle created: $Dist"
