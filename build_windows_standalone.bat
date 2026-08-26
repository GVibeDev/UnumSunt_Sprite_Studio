@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows_standalone.ps1" %*
if errorlevel 1 (
    echo.
    echo R5c8 BUILD FAILED.
    pause
    exit /b 1
)
echo.
echo R5c8 build completed.
pause
endlocal
