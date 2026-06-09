@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo  Setup development environment
echo ============================================================
echo.

set "PY_CMD="

where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"

if "%PY_CMD%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)

if "%PY_CMD%"=="" (
  echo [ERROR] Python was not found.
  echo Install Python 3.10+ and check "Add Python to PATH".
  pause
  exit /b 1
)

echo [INFO] Python command: %PY_CMD%

if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creating .venv...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv.
    pause
    exit /b 1
  )
)

echo [INFO] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] pip upgrade failed.
  pause
  exit /b 1
)

echo [INFO] Installing runtime requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] requirements install failed.
  pause
  exit /b 1
)

if exist "requirements-dev.txt" (
  echo [INFO] Installing developer requirements...
  ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
)

echo.
echo [OK] Development environment is ready.
echo Run: .\START_WINDOWS.bat
pause
