@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo  Save current work to GitHub
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

echo [INFO] Current changes:
"%GIT_CMD%" status --short
echo.

for /f "delims=" %%S in ('"%GIT_CMD%" status --porcelain') do goto :has_changes
echo [OK] No changes to save.
pause
exit /b 0

:has_changes
set "COMMIT_MSG="
set /p COMMIT_MSG=Commit message: 
if "%COMMIT_MSG%"=="" set "COMMIT_MSG=Update project"

"%GIT_CMD%" add -A
if errorlevel 1 (
  echo [ERROR] git add failed.
  pause
  exit /b 1
)

"%GIT_CMD%" commit -m "%COMMIT_MSG%"
if errorlevel 1 (
  echo [ERROR] git commit failed.
  pause
  exit /b 1
)

echo.
echo [INFO] Syncing with GitHub before push...
"%GIT_CMD%" %GIT_AUTH_ARGS% pull --rebase origin main
if errorlevel 1 (
  echo.
  echo [ERROR] Rebase failed. Resolve conflicts, then run:
  echo git add .
  echo git rebase --continue
  echo git push origin main
  pause
  exit /b 1
)

"%GIT_CMD%" %GIT_AUTH_ARGS% push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] Push failed. Check GitHub login or network status.
  pause
  exit /b 1
)

echo.
echo [OK] Work saved to GitHub.
pause
