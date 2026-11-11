<#
.SYNOPSIS
  Build a standalone Windows app (dist\Linger\Linger.exe) and a zip for releases.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
#>
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Select-String -Path "src\linger\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
Write-Host "Building Linger $version" -ForegroundColor Cyan

python -m pip install --upgrade -e ".[dev]" | Out-Null
python scripts\make_icon.py
python -m pytest -q

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }

python -m PyInstaller `
  --noconfirm --clean --windowed `
  --name Linger `
  --icon assets\icon.ico `
  --paths src `
  --collect-submodules linger `
  --exclude-module tkinter `
  run.pyw

$zip = "dist\Linger-$version-win64.zip"
Compress-Archive -Path dist\Linger\* -DestinationPath $zip -Force
Write-Host "Done: dist\Linger\Linger.exe" -ForegroundColor Green
Write-Host "Release zip: $zip" -ForegroundColor Green
