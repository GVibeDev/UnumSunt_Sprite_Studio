@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows_standalone.ps1" %*
if errorlevel 1 (
    echo.
    echo BUILD R5c6a FALLITA.
    pause
    exit /b 1
)
echo.
echo Build R5c6a completata.
pause
endlocal
