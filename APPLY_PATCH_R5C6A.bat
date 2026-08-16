@echo off
setlocal
cd /d "%~dp0"

echo === Unum Sunt Sprite Studio R5c6a - Krea 2 Managed Component Completion ===
echo Pulizia dei soli file obsoleti della baseline R5c6...

if exist "installer\UnumSuntSpriteStudio_R5c6.iss" (
  del /f /q "installer\UnumSuntSpriteStudio_R5c6.iss"
  if errorlevel 1 (
    echo ERRORE: impossibile eliminare installer\UnumSuntSpriteStudio_R5c6.iss
    pause
    exit /b 1
  )
)

if exist "PATCH_MANIFEST_R5C6A.json" del /f /q "PATCH_MANIFEST_R5C6A.json" >nul 2>&1

echo Patch R5c6a applicata. Nessun runtime, modello o progetto utente e' stato modificato.
endlocal
(goto) 2>nul & del "%~f0"
