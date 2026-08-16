# Migration R5c3e → R5c4

R5c4 adds the first real Windows Setup bootstrapper on top of the validated R5c3e runtime/adoption architecture.

## Added
- `installer/UnumSuntSpriteStudio_R5c4.iss`
- `build_setup_windows.bat`
- `build_setup_windows.ps1`
- runtime discovery CLI: `--runtime-discover`
- setup adoption CLI: `--runtime-auto-adopt`
- conservative automatic adoption of the first healthy discovered external runtime
- Setup-side Core / Complete / Custom installation modes
- setup reports under `%LOCALAPPDATA%/UnumSuntSpriteStudio/setup`

## Preserved
- no Python requirement on target machines for the Core
- Python 3.13.x remains build-only
- Python 3.11 remains private to WanGP
- no arbitrary RAM/VRAM/model blacklist
- existing external runtimes are never moved or renamed
