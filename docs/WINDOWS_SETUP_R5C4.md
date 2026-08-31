# R5c4 — Windows Setup Bootstrapper

## Goal
Produce a real Windows installer for Unum Sunt Sprite Studio from the validated standalone/runtime line.

The Setup installs the frozen Core and can optionally orchestrate the existing R5c2/R5c3 runtime APIs. It never requires Python on the target machine.

## Build
Run:

```bat
build_setup_windows.bat
```

The build pipeline:

1. builds/tests the canonical Windows standalone Core;
2. locates Inno Setup `ISCC.exe`;
3. can install Inno Setup through WinGet when missing;
4. compiles `installer/UnumSuntSpriteStudio_R5c4.iss`;
5. writes SHA-256 for the final Setup executable.

Expected output:

```text
release/installer/
  UnumSunt_Sprite_Studio_R5c4_Setup_x64.exe
  UnumSunt_Sprite_Studio_R5c4_Setup_x64_SHA256.txt
```

## Installation modes

- **Core**: Sprite Studio only; no local AI downloads.
- **Complete R5c4**: Core + local WanGP runtime + Wan Animate. Krea 2 remains scheduled for R5c5.
- **Custom**: choose runtime/Animate independently.

## Runtime orchestration

If AI is selected, Setup:

1. runs the existing runtime preflight before any heavy AI download;
2. can automatically discover and adopt an existing valid WanGP installation;
3. if adoption fails and fallback is enabled, installs the managed runtime;
4. runs a final runtime health check.

Existing adopted runtimes are registered as `ownership=external` and are never moved, renamed or destructively repaired by Setup.

## Paths
The user can choose separate locations for:

- Runtime AI
- Models

This allows the runtime to remain on the system disk while large model files live on another drive.

## Uninstall policy
The Windows uninstaller removes the installed Core. User projects, application state, adopted external runtimes and external model folders are not deleted automatically.

## R5c4 scope boundary
Krea 2 gated download/license/token flow is intentionally not part of the Setup bootstrapper yet. That remains the next managed-components milestone (R5c5).
