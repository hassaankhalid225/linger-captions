<#
.SYNOPSIS
  Build a standalone Windows app (dist\LiveCaptionRecorder\LiveCaptionRecorder.exe) and a zip for releases.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
#>
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Select-String -Path "src\live_caption_recorder\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
Write-Host "Building Live Caption Recorder $version" -ForegroundColor Cyan

python -m pip install --upgrade -e ".[dev]" | Out-Null
python scripts\make_icon.py
python -m pytest -q

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }

python -m PyInstaller `
  --noconfirm --clean --windowed `
  --name LiveCaptionRecorder `
  --icon assets\icon.ico `
  --paths src `
  --collect-submodules live_caption_recorder `
  --exclude-module tkinter `
  run.pyw

$zip = "dist\LiveCaptionRecorder-$version-win64.zip"
Compress-Archive -Path dist\LiveCaptionRecorder\* -DestinationPath $zip -Force
Write-Host "Done: dist\LiveCaptionRecorder\LiveCaptionRecorder.exe" -ForegroundColor Green
Write-Host "Release zip: $zip" -ForegroundColor Green
