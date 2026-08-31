# Unum Sunt Sprite Studio R5c8 — International Release UX

R5c8 is the first release candidate prepared specifically for international distribution through itch.io.
It keeps the validated R5c7 production pipeline and focuses on public-facing usability, packaging and licensing clarity.

## What changed

- English is now the default and supported application UI language for the public build.
- Main workspaces, dialogs, status/error messages and local-runtime diagnostics were translated to English.
- A built-in offline **Help** menu now provides:
  - Quick Start;
  - Production Workflow;
  - Local AI setup guidance;
  - controls and practical tips;
  - licensing information.
- The installer no longer presents the GNU GPL as a click-through agreement. It shows an informational open-source notice instead.
- `OPEN_SOURCE_LICENSE_NOTICE.txt` is bundled with the standalone Core and public package.
- Krea 2 and Miniconda/Anaconda acceptances remain explicit and separate because they govern optional third-party components.
- Windows product metadata was advanced to `5.8.0.0` / `R5c8`.
- The Setup output is now `UnumSunt_Sprite_Studio_R5c8_Setup_x64.exe`.
- The standalone output is now `UnumSunt_Sprite_Studio_R5c8_Windows_x64_Standalone.zip`.
- The application and Setup continue to use the multi-resolution `assets/branding/app_icon.ico`.
- New R5c8 release tests verify version identity, English navigation/help, GPL notice behavior, icon sizes and public-release wiring.

## Compatibility and architecture

The underlying Core architecture remains the R5c7 line:

- Windows x64 Core packaged with PyInstaller;
- Inno Setup installer;
- optional managed/adopted WanGP runtime;
- Wan 2.2 Animate support;
- Krea 2 Turbo image-generation support;
- Prompt Builder, Calibration Lab, Production Presets and Guided Workflows;
- Sprite Sheet import/decomposition/reference workflow;
- Extraction, Clean-up, Alignment, Smart Selection, Character Set / Layer Manager and export;
- non-destructive runtime ownership and maintenance rules.

R5c8 does not bundle WanGP, Krea model weights or other external AI runtimes into the GPL-covered Core.

## Licensing

The project-owned Core remains **GNU GPL-3.0-or-later**.
A paid itch.io download is a paid packaged distribution of the GPL Core; it does not convert the Core into proprietary software.
The Corresponding Source for the distributed release must be supplied or made available to purchasers at no additional charge.

Third-party components remain under their respective licenses and terms. See:

- `LICENSE`
- `OPEN_SOURCE_LICENSE_NOTICE.txt`
- `THIRD_PARTY_NOTICES.txt`
- `KREA_SAFETY_AND_USE.txt`
- `GPL_DISTRIBUTION_CHECKLIST.txt`

## Validation state

Automated regression after the R5c8 internationalization patch: **329 tests passed** plus `compileall`.

Before publishing the itch.io binaries, complete the Windows manual validation gates in `PUBLIC_RELEASE_CHECKLIST_R5c8.md`, including installer UI/icon behavior, installed application startup, Help content, optional AI-runtime flow and uninstall/maintenance behavior.
