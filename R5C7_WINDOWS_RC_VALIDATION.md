# R5c7 Windows RC Validation

Eseguire `VALIDATE_R5C7_WINDOWS.bat` sul PC Windows reale.

## Modalità
1. **Build + validate Setup R5c7** — esegue la build canonica e poi i controlli.
2. **Validate existing build only** — non ricompila; verifica gli artefatti già presenti.
3. **Build + validate + Inno bootstrap** — come 1, ma autorizza il bootstrap WinGet di Inno Setup se necessario.

## Controlli automatici
- presenza asset branding;
- contratto icona PyInstaller e branding Inno Setup;
- `pip check` del Core build environment;
- versione del frozen EXE;
- version resource Windows;
- estrazione automatica dell'icona associata all'EXE;
- frozen self-check;
- Setup R5c7 e SHA-256;
- `pip check` del/i runtime WanGP configurati in `%LOCALAPPDATA%\UnumSuntSpriteStudio`.

## Output
I report vengono scritti in `release\audit\`:
- `R5c7_WINDOWS_RC_VALIDATION.json`
- `R5c7_WINDOWS_RC_VALIDATION.txt`
- `exe_icon_preview.png` quando Windows consente l'estrazione dell'icona.

## Gate manuali
Install/update/repair/uninstall e generazioni AI reali restano volutamente marcati WARN finché non vengono verificati dall'autore sulla macchina Windows reale.
