@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_CMD="
set "PORT=8520"

title Kakao Emoticon v100

echo.
echo ============================================================
echo  Kakao Emoticon Maker v100 Clean
echo ============================================================
echo.

where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"

if "%PY_CMD%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)

if "%PY_CMD%"=="" (
  echo [ERROR] Python was not found.
  echo Install Python 3.10+ and enable "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [v100] Creating local Python environment...
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto PYTHON_ERROR
)

call ".venv\Scripts\activate.bat"

if not exist ".venv\v100_ready.txt" (
  echo [v100] Installing required packages...
  python -m pip install --upgrade pip
  if errorlevel 1 goto PACKAGE_ERROR
  python -m pip install -r requirements.txt
  if errorlevel 1 goto PACKAGE_ERROR
  echo ready> ".venv\v100_ready.txt"
)

python scripts\stop_port.py %PORT%

echo.
echo [v100] Starting app.
echo [v100] Local URL: http://127.0.0.1:%PORT%
echo.
python app.py
goto :end

:PYTHON_ERROR
echo [ERROR] Python virtual environment could not be created.
pause
exit /b 1

:PACKAGE_ERROR
echo [ERROR] Package installation failed.
pause
exit /b 1

:end
endlocal
