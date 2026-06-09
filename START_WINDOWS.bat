@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_DIR=%~dp0"
set "PORT=8520"
set "PY_CMD="
if exist ".venv\Scripts\python.exe" set "PY_CMD=.venv\Scripts\python.exe"

title Kakao Emoticon v100 Launcher

echo.
echo ============================================================
echo  Kakao Emoticon Maker v100 Clean - First Run Launcher
echo ============================================================
echo [v100] APP_DIR=%APP_DIR%
echo [v100] PORT=%PORT%
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
  echo [ERROR] Python was not found.
  echo Install Python 3.10+ and enable "Add Python to PATH".
  pause
  exit /b 1
)

if not exist "app.py" (
  echo [ERROR] app.py was not found.
  echo Please run this file from the extracted program folder.
  pause
  exit /b 1
)

echo [v100] Python command: %PY_CMD%

if not exist ".venv\Scripts\python.exe" (
  echo [v100] Creating local Python environment...
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto PYTHON_ERROR
)

call .venv\Scripts\activate.bat
python --version

if not exist ".venv\v100_ready.txt" (
  echo [v100] Installing required packages...
  python -m pip install --upgrade pip
  if errorlevel 1 goto PACKAGE_ERROR
  python -m pip install -r requirements.txt
  if errorlevel 1 goto PACKAGE_ERROR
  echo ready> .venv\v100_ready.txt
) else (
  echo [v100] Python environment already prepared.
)

echo [v100] Stopping existing server on port %PORT% if needed...
if exist "scripts\stop_port.py" python scripts\stop_port.py %PORT%

echo [v100] Starting local web server...
start "Kakao Emoticon v100 Server" cmd /k "cd /d ""%APP_DIR%"" && call .venv\Scripts\activate.bat && set KAKAO_NO_BROWSER=1 && python app.py"

echo [v100] Waiting for server...
if exist "scripts\wait_for_port.py" (
  python scripts\wait_for_port.py 127.0.0.1 %PORT% 60
) else (
  timeout /t 3 /nobreak >nul
)

echo [v100] Opening browser: http://127.0.0.1:%PORT%
start "" http://127.0.0.1:%PORT%

echo.
echo [v100] App address: http://127.0.0.1:%PORT%
echo [v100] If the browser does not open, copy the address above into Chrome or Edge.
echo.
pause
exit /b 0

:PYTHON_ERROR
echo [ERROR] Python virtual environment could not be created.
echo Check Python installation and folder permissions.
pause
exit /b 1

:PACKAGE_ERROR
echo [ERROR] Package installation failed.
echo Check internet connection, then run this file again.
pause
exit /b 1
