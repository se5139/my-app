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

set "GIT_AUTH_ARGS="
where gh >nul 2>nul
if not errorlevel 1 (
  gh auth status >nul 2>nul
  if not errorlevel 1 (
    set "ASKPASS=%TEMP%\kakao_git_askpass_gh.cmd"
    > "!ASKPASS!" echo @echo off
    >> "!ASKPASS!" echo echo %%~1 ^| findstr /I "Username" ^>nul
    >> "!ASKPASS!" echo if not errorlevel 1 ^(
    >> "!ASKPASS!" echo   echo x-access-token
    >> "!ASKPASS!" echo   exit /b 0
    >> "!ASKPASS!" echo ^)
    >> "!ASKPASS!" echo gh auth token
    set "GIT_TERMINAL_PROMPT=0"
    set "GIT_ASKPASS=!ASKPASS!"
    set "GIT_AUTH_ARGS=-c credential.helper= -c core.askPass=!ASKPASS!"
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
"%GIT_CMD%" %GIT_AUTH_ARGS% pull --ff-only origin main
if errorlevel 1 (
  echo.
  echo [ERROR] Pull failed. Check the message above.
  pause
  exit /b 1
)

echo.
echo [OK] Latest files are ready.
pause
