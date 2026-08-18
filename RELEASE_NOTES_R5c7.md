# Unum Sunt Sprite Studio R5c7 — Release Notes

R5c7 is the first validated Windows release baseline of Unum Sunt Sprite Studio. It packages the production pipeline as a standalone Windows x64 application while keeping local AI runtimes and model weights outside the Core bundle.

## Main capabilities

- video import, frame extraction and sprite preparation;
- chroma/background cleanup, alpha editing and painter workflow;
- alignment, pivot/anchor tools, loop preview and spritesheet export;
- project persistence, Project Groups and Character Set / Layer Manager;
- guided production workflows and reusable Production Presets;
- local WanGP bridge for Wan Animate and Krea 2 Turbo;
- managed or adopted external AI runtime with health/preflight checks;
- Image Gen memory profiles and reserved-RAM control;
- Windows update/repair/uninstall lifecycle with independent preservation/removal choices for managed runtime, models and user data.

## R5c7 release hardening

R5c7 includes the release-candidate hardening completed after R5c6b: safe managed ZIP extraction, immutable upstream revision pins for the validated managed runtime path, PySide6 compatibility fixes, Clean-up source-transition protection, Pillow deprecation cleanup, branded Windows packaging and reproducible validation tooling.

## Licensing

The project-owned Sprite Studio Core is released under **GNU GPL-3.0-or-later**. WanGP, Krea 2, Wan Animate and other third-party components retain their own licenses and notices. See `LICENSE` and `THIRD_PARTY_NOTICES.txt`.

Krea generation includes a pre-generation policy acknowledgement and a manual review step before a generated image can be promoted to the WAN reference pipeline. See `KREA_SAFETY_AND_USE.txt`.

## Distribution model

The Windows Setup always installs the Core. AI components are optional. WanGP/Miniconda/PyTorch/model weights are not embedded into the Core executable: they are external resources managed or adopted through the Runtime Manager.

## Validation

The final source line passes **322 automated tests** and `compileall`. The Windows validation pipeline passed standalone/Setup build, Core and WanGP dependency checks, frozen self-check, embedded icon/version resources and installer checksum generation. Manual author validation covered installed startup/branding, real generation workflows, Character/project switching, uninstall preservation behavior and the final GPL/Krea compliance flow.

## Known distribution note

The current Windows build pipeline does not apply an Authenticode code-signing certificate. Depending on Windows reputation/SmartScreen state, downloaded binaries may therefore display an unknown-publisher warning. This is a distribution/reputation issue rather than an application integrity failure; published SHA-256 checksums should be used to verify downloads.
