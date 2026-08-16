# R5c7 — GPL & Compliance Finalization

Status: TEST CANDIDATE above validated `UnumSunt_Sprite_Studio_R5c7`.

## Core license

The project-owned Unum Sunt Sprite Studio Core is now declared as `GPL-3.0-or-later`.
The complete GNU GPL version 3 text is included in `LICENSE`.

## License separation

WanGP, Krea 2, Miniconda, PyTorch and AI model weights remain separate third-party
components and are not relicensed under the Core GPL. WanGP remains an external CLI
runtime. Krea remains an optional separately licensed model component.

## Krea safeguard

The Image Gen workspace adds:

- pre-generation Krea license/AUP attestation;
- no automatic Krea output hand-off to WAN;
- mandatory manual output review before `Usa come reference WAN`;
- minimal `krea_safety_review.json` sidecar in the job directory after approval;
- direct links to the current Krea license and AUP.

The sidecar contains no prompt text, tokens or user identity.

## Windows release compliance

- Inno Setup displays `LICENSE` as the installer license page.
- The PyInstaller bundle includes GPL and project compliance documents.
- `tools/collect_release_licenses.py` collects actual license/notice files from the
  Python 3.13 build environment into `build/legal` before PyInstaller runs.
- The generated inventory is bundled under `licenses/` in the frozen application.

## Automated verification

- `python -m unittest discover -s tests -p "test_*.py"`: 322 tests PASS.
- `compileall app main.py tools`: PASS.
- Krea managed template recognition: `krea2_turbo` recognized and policy applies.

## Manual release gates after patch

1. rebuild standalone + Setup on Windows;
2. confirm installer GPL license page and installed legal files;
3. generate one Krea image and verify the pre-generation attestation;
4. verify the output is NOT automatically promoted to WAN;
5. approve the output and verify `Usa come reference WAN` becomes available;
6. verify `krea_safety_review.json` exists in the job directory;
7. publish/provide Corresponding Source for the exact public binary revision.
