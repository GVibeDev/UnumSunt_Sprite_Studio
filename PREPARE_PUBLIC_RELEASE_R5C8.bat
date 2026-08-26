@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\prepare_public_release.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo.
if not "%RC%"=="0" echo PUBLIC RELEASE PREPARATION FAILED - exit code %RC%
if not "%RC%"=="0" pause
exit /b %RC%
