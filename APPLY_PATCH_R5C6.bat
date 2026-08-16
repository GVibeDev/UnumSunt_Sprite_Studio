@echo off
setlocal
cd /d "%~dp0"
if exist "installer\UnumSuntSpriteStudio_R5c4a.iss" (
  del /q "installer\UnumSuntSpriteStudio_R5c4a.iss"
  echo Rimosso installer\UnumSuntSpriteStudio_R5c4a.iss
)
echo Patch R5c6: pulizia completata.
endlocal
