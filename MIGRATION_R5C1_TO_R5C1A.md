# Migration R5c1 → R5c1a

## Scope
R5c1a integrates product branding into the Windows standalone line:

- application icon for source run and frozen EXE
- startup splash screen
- dynamic splash metadata overlay
- packaged branding assets for PyInstaller builds

## Added assets
- `assets/branding/app_icon.png`
- `assets/branding/app_icon.ico`
- `assets/branding/splash_screen.png`

## New module
- `app/branding.py`

## Runtime behavior
- the application loads a branded icon when available
- a splash screen is shown on startup before the main window appears
- splash metadata is rendered from `app/version.py`, so future builds can update version/build/licence details without editing the image itself
