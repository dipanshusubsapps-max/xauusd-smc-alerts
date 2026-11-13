# XAUUSD SMC Alert System - PowerShell Runner
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       XAUUSD SMC ALERT SYSTEM - LOCAL RUNNER" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Run SMC Health Check"
Write-Host "2. Run Single Check (Dry-Run Mode)"
Write-Host "3. Run Historical Replay Test"
Write-Host "4. Run Pytest Test Suite"
Write-Host "5. Test Telegram Connection"
Write-Host "6. Exit"
Write-Host ""

$choice = Read-Host "Enter your choice (1-6)"

switch ($choice) {
    "1" { & $PythonExe main.py --health-check }
    "2" { & $PythonExe main.py --dry-run }
    "3" { & $PythonExe main.py --replay data\sample_xauusd_m5.csv }
    "4" { & $PythonExe -m pytest -v }
    "5" { & $PythonExe main.py --test-telegram }
    Default { Write-Host "Exiting." }
}
