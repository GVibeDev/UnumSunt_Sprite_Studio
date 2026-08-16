@echo off
setlocal
cd /d "%~dp0"
echo === Unum Sunt Sprite Studio R5c7 - Windows RC Hardening Candidate ===
echo Pulizia dei soli file sorgente obsoleti della linea R5c6a/R5c6b...

if exist "installer\UnumSuntSpriteStudio_R5c6.iss" del /f /q "installer\UnumSuntSpriteStudio_R5c6.iss"
if exist "installer\UnumSuntSpriteStudio_R5c6a.iss" del /f /q "installer\UnumSuntSpriteStudio_R5c6a.iss"
if exist "R5C6A_IMAGE_MEMORY_HOTFIX_TEST.md" del /f /q "R5C6A_IMAGE_MEMORY_HOTFIX_TEST.md"
if exist "TEST_REPORT_R5C6A_IMAGE_MEMORY_HOTFIX.txt" del /f /q "TEST_REPORT_R5C6A_IMAGE_MEMORY_HOTFIX.txt"
if exist "R5C6A_CUMULATIVE_HOTFIX_TEST_2.md" del /f /q "R5C6A_CUMULATIVE_HOTFIX_TEST_2.md"
if exist "APPLY_PATCH_R5C6A.bat" del /f /q "APPLY_PATCH_R5C6A.bat"
if exist "PATCH_MANIFEST_R5C6A.json" del /f /q "PATCH_MANIFEST_R5C6A.json"
if exist "PATCH_MANIFEST_R5C6A_IMAGE_MEMORY_HOTFIX.json" del /f /q "PATCH_MANIFEST_R5C6A_IMAGE_MEMORY_HOTFIX.json"
if exist "PATCH_MANIFEST_R5C6A_CUMULATIVE_HOTFIX_TEST_2.json" del /f /q "PATCH_MANIFEST_R5C6A_CUMULATIVE_HOTFIX_TEST_2.json"

echo Patch R5c7 applicata. Runtime, modelli e dati utente non sono stati modificati.
endlocal
