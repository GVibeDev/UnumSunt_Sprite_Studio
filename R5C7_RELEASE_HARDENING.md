# R5c7 — Windows Release Candidate Hardening

Status: TEST CANDIDATE. Baseline input: validated R5c6b.

## Included hardening

- Active version/build identity promoted to R5c7 / 5.7.0.0.
- Application-version metadata is sourced from `app.version.APP_VERSION` in active persistence/export paths.
- Deprecated Pillow `Image.fromarray(..., mode=...)` calls removed.
- Managed WanGP ZIP extraction rejects absolute paths, Windows drive paths, `..` traversal and symlink members before writing any archive member.
- Managed WanGP source pinned to immutable commit `6e35b37e309ccebeed193ef53cdff66fb973b693` (WanGP 12.53 line at audit time).
- Managed Krea 2 repository revision pinned to `f7a3040b990b672af3c30b5ad1f0df8ffd244881`; managed template URLs use the same immutable revision.
- `.gitignore` expanded for secrets, build/release products, local runtimes and model weights.
- Installer/build names and Windows version resource promoted to R5c7 while preserving the existing Inno Setup AppId for update/repair continuity.

## Automated gate

- Python compileall: PASS.
- Full unittest discovery: 301 tests, PASS.

## Still open before public release

- Core license selection and final `LICENSE`.
- `THIRD_PARTY_NOTICES`.
- Krea 2 application-level safeguard/content-filtering gate.
- `pip check` on the actual Windows Core build venv and the actual WanGP Python 3.11 runtime.
- Windows clean install, update, repair, conservative uninstall and full uninstall matrix.
- Real Animate/Krea/Image→Animate/Video→Sprite GPU workflow checks.

R5c7 must not be promoted to a validated/public baseline until the author completes the real Windows manual gate.
