# R5c7 Public Release Checklist

Use this checklist for the exact public tag/build that will be uploaded.

## Source

- [ ] working tree contains only intended R5c7 release files;
- [ ] `python -m unittest discover -s tests -p "test_*.py"` passes;
- [ ] `python -m compileall app main.py` passes;
- [ ] `python main.py --version` reports `Unum Sunt Sprite Studio R5c7`;
- [ ] `LICENSE`, `THIRD_PARTY_NOTICES.txt`, `KREA_SAFETY_AND_USE.txt` and `SECURITY.md` are present;
- [ ] no `.env`, tokens, private keys, local runtime state, generated jobs, model weights or personal absolute paths are included;
- [ ] final source revision is committed and tagged `R5c7`.

## Windows build

- [ ] run `PREPARE_PUBLIC_RELEASE_R5C7.bat`;
- [ ] Core `pip check` passes;
- [ ] WanGP `pip check` passes on the validated runtime;
- [ ] standalone frozen self-check passes;
- [ ] Setup builds successfully;
- [ ] EXE/Setup branding and version resources are correct;
- [ ] installer GPL page appears;
- [ ] Krea acknowledgement/review gate works.

## Publish these artifacts together

- [ ] `UnumSunt_Sprite_Studio_R5c7_Setup_x64.exe`;
- [ ] Setup SHA-256 file;
- [ ] `UnumSunt_Sprite_Studio_R5c7_Windows_x64_Standalone.zip`;
- [ ] standalone SHA-256 file;
- [ ] `UnumSunt_Sprite_Studio_R5c7_Source.zip` (GPL Corresponding Source);
- [ ] source SHA-256 file;
- [ ] `RELEASE_MANIFEST_R5c7.json`;
- [ ] `RELEASE_NOTES_R5c7.md`;
- [ ] `LICENSE` and `THIRD_PARTY_NOTICES.txt`.

## Git / GitHub

Recommended release tag: `R5c7`.

```text
git add -A
git commit -m "Release Unum Sunt Sprite Studio R5c7"
git tag -a R5c7 -m "Unum Sunt Sprite Studio R5c7"
git push origin <branch>
git push origin R5c7
```

Create a GitHub Release from tag `R5c7`, paste `RELEASE_NOTES_R5c7.md`, and attach the artifacts generated under `release\public\R5c7`. Do not upload local runtimes, model checkpoints, `.env` files or project/user data.

## Windows reputation

The current build is not Authenticode-signed. A SmartScreen/unknown-publisher warning can occur for a new binary. Publish SHA-256 checksums prominently. Code signing can be added in a future release without changing the Core license.
