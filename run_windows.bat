@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_windows.ps1" %*
if errorlevel 1 (
    echo.
    echo SOURCE STARTUP FAILED.
    pause
    exit /b 1
)
endlocal
