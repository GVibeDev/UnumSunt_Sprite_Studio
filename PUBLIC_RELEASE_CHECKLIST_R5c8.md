# Unum Sunt Sprite Studio R5c8 — Public Release Checklist

Use this checklist before replacing the itch.io R5c6/R5c7 draft artifacts with R5c8.

## Source and build

- [ ] Working tree is clean and all R5c8 changes are committed.
- [ ] `python -m unittest discover -s tests -p "test_*.py"` passes (expected current count: 329).
- [ ] `python -m compileall app main.py` passes.
- [ ] `PREPARE_PUBLIC_RELEASE_R5C8.bat` completes successfully.
- [ ] Standalone ZIP SHA-256 is generated.
- [ ] Setup EXE SHA-256 is generated.
- [ ] Corresponding Source ZIP SHA-256 is generated.
- [ ] `release/public/R5c8/RELEASE_MANIFEST_R5c8.json` is present.

## Installer UX

- [ ] Setup title/version shows R5c8.
- [ ] Setup taskbar/window icon uses the Sprite Studio multi-resolution icon, not the generic Inno icon.
- [ ] Installer UI is English.
- [ ] GPL is presented as an informational open-source notice; there is no forced GPL acceptance checkbox/page.
- [ ] Core / Complete / Custom installation types are readable and correct.
- [ ] Miniconda/Anaconda acceptance is required only when managed fallback installation is selected.
- [ ] Krea 2 License + AUP acceptance is required only when Krea 2 is selected.

## Installed Core

- [ ] Start-menu shortcut launches the application.
- [ ] Optional Desktop shortcut launches the application.
- [ ] Application window/taskbar icon is correct.
- [ ] Application title shows R5c8.
- [ ] Main UI is English.
- [ ] Help → Quick Start opens.
- [ ] Help → Production Workflow opens.
- [ ] Help → Local AI Setup opens.
- [ ] Help → About & Licensing opens.
- [ ] `LICENSE`, `OPEN_SOURCE_LICENSE_NOTICE.txt`, `THIRD_PARTY_NOTICES.txt` and `KREA_SAFETY_AND_USE.txt` are present in the standalone distribution.

## Core workflow smoke test

- [ ] Create/open a project.
- [ ] Open an existing video or spritesheet.
- [ ] Extraction workspace works.
- [ ] Clean-up workspace works.
- [ ] Alignment workspace works.
- [ ] Smart Selection works.
- [ ] Character Set / Layer Manager works.
- [ ] Export produces expected frames/spritesheet.

## Optional local AI

- [ ] Runtime preflight opens in English.
- [ ] Runtime Manager opens in English.
- [ ] Existing WanGP runtime detection/adoption remains non-destructive.
- [ ] Managed runtime install/repair path remains functional where applicable.
- [ ] Krea 2 generation attestation and post-generation review gate remain functional.
- [ ] Wan Animate generation path remains functional.

## Maintenance

- [ ] Update/repair preserves external/adopted runtimes.
- [ ] Uninstall asks independently about managed runtime, managed models and user data.
- [ ] External/adopted runtime is never removed automatically.

## itch.io publication

- [ ] Upload `UnumSunt_Sprite_Studio_R5c8_Setup_x64.exe`.
- [ ] Upload `UnumSunt_Sprite_Studio_R5c8_Windows_x64_Standalone.zip`.
- [ ] Upload `UnumSunt_Sprite_Studio_R5c8_Source.zip` with no additional charge.
- [ ] Publish/update SHA-256 values where appropriate.
- [ ] Page text identifies the Core as GPL-3.0-or-later and the $9.99 price as the packaged distribution price.
- [ ] Payment provider is configured before enabling purchases.
