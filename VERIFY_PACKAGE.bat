@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_CMD="
if exist ".venv\Scripts\python.exe" set "PY_CMD=.venv\Scripts\python.exe"

title Kakao Emoticon v100 Package Check

echo.
echo ============================================================
echo  Kakao Emoticon Maker v100 Clean - Package Check
echo ============================================================
echo [check] This verifies the extracted portable package.
echo.

if "%PY_CMD%"=="" (
  where py >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3"
)

if "%PY_CMD%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)

if "%PY_CMD%"=="" (
  if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PY_CMD=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

if "%PY_CMD%"=="" (
  echo [FAIL] Python was not found.
  echo Install Python 3.10+ and enable "Add Python to PATH".
  pause
  exit /b 1
)

%PY_CMD% scripts\verify_package.py
if errorlevel 1 (
  echo.
  echo [FAIL] Package check found a problem.
  pause
  exit /b 1
)

echo.
echo [OK] Package check passed. You can run START_WINDOWS.bat.
pause
exit /b 0
