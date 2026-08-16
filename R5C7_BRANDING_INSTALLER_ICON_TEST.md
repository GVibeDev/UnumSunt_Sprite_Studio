# R5c7 Branding / Installer / EXE Icon Test Patch

Patch incrementale sopra la baseline di test R5c7 RC hardening.

## Obiettivi
- applicare il logo all'installer Inno Setup;
- aggiungere immagini brandizzate al wizard di installazione;
- rafforzare l'identità dell'EXE Windows con AppUserModelID esplicito;
- preferire l'icona `.ico` in runtime su Windows;
- aggiungere regression test dedicati al branding.

## File modificati
- `app/version.py`
- `app/branding.py`
- `main.py`
- `installer/UnumSuntSpriteStudio_R5c7.iss`
- `tests/test_branding_integration.py`
- `assets/branding/installer_wizard.bmp`
- `assets/branding/installer_wizard_small.bmp`

## Note
- nessuna modifica a runtime AI, modelli, dati utente o pipeline core;
- PyInstaller continua a usare `assets/branding/app_icon.ico` per l'EXE;
- l'installer ora usa anche `WizardImageFile` e `WizardSmallImageFile` brandizzati.
