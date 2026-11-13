@echo off
setlocal
echo ========================================================
echo        XAUUSD SMC ALERT SYSTEM - LOCAL LAUNCHER
echo ========================================================
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo.
echo Select an option:
echo 1. Run SMC Health Check
echo 2. Run Single Check (Dry-Run Mode)
echo 3. Run Historical Replay Test
echo 4. Run Pytest Test Suite
echo 5. Test Telegram Connection
echo 6. Exit
echo.

set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" (
    "%PYTHON_EXE%" main.py --health-check
) else if "%choice%"=="2" (
    "%PYTHON_EXE%" main.py --dry-run
) else if "%choice%"=="3" (
    "%PYTHON_EXE%" main.py --replay data\sample_xauusd_m5.csv
) else if "%choice%"=="4" (
    "%PYTHON_EXE%" -m pytest -v
) else if "%choice%"=="5" (
    "%PYTHON_EXE%" main.py --test-telegram
) else (
    echo Exiting.
)

pause
