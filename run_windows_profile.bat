@echo off
setlocal
cd /d "%~dp0"
set "UNUM_SUNT_PERF=1"
set "UNUM_SUNT_PERF_REPORT=%~dp0performance_report_R5e13b.json"
call run_windows.bat
endlocal
