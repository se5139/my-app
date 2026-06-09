@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo  Pull latest before work
echo ============================================================
echo.

set "GIT_CMD=git"
where git >nul 2>nul
if errorlevel 1 (
  set "GIT_CMD="
  for /d %%D in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do (
    if exist "%%~fD\resources\app\git\cmd\git.exe" set "GIT_CMD=%%~fD\resources\app\git\cmd\git.exe"
  )
  if "!GIT_CMD!"=="" (
    echo [ERROR] Git is not installed or not in PATH.
    echo Install Git for Windows first: https://git-scm.com/download/win
    pause
    exit /b 1
  )
)

"%GIT_CMD%" rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
  echo [ERROR] This folder is not a Git repository.
  echo Clone again: git clone https://github.com/se5139/my-app.git
  pause
  exit /b 1
)

for /f "delims=" %%S in ('"%GIT_CMD%" status --porcelain') do (
  echo [STOP] You have local changes.
  echo Save or back up your work before pulling latest files.
  echo.
  "%GIT_CMD%" status --short
  pause
  exit /b 1
)

echo [INFO] Local folder is clean. Pulling latest main branch...
"%GIT_CMD%" pull --ff-only origin main
if errorlevel 1 (
  echo.
  echo [ERROR] Pull failed. Check the message above.
  pause
  exit /b 1
)

echo.
echo [OK] Latest files are ready.
pause
