@echo off
setlocal
cd /d "%~dp0"
echo === Unum Sunt Sprite Studio R5c7 - Windows RC Validation ===
echo.
echo 1. Build + validate Setup R5c7
echo 2. Validate existing build only
echo 3. Build + validate and allow Inno Setup bootstrap
echo.
set /p choice=Choice [1/2/3]: 
if "%choice%"=="2" goto existing
if "%choice%"=="3" goto inno
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0validate_windows_rc.ps1" -BuildSetup
goto end
:existing
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0validate_windows_rc.ps1" -SkipBuild
goto end
:inno
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0validate_windows_rc.ps1" -BuildSetup -InstallInnoSetup
:end
set rc=%ERRORLEVEL%
echo.
if not "%rc%"=="0" echo Validation returned exit code %rc%.
pause
exit /b %rc%
