@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_setup_windows.ps1" %*
if errorlevel 1 (
  echo.
  echo R5c8 SETUP BUILD FAILED.
  pause
  exit /b 1
)
echo.
echo R5c8 Setup build completed.
pause
