@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_setup_windows.ps1" %*
if errorlevel 1 (
  echo.
  echo BUILD SETUP R5c6a FALLITA.
  pause
  exit /b 1
)
echo.
echo Build Setup R5c6a completata.
pause
