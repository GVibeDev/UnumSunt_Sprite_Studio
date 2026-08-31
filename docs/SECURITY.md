# Security Policy

## Supported release

Security fixes are currently targeted at the latest validated release line, **R5c7**, and subsequent releases. Historical development milestones are retained for traceability but are not supported release branches.

## Reporting a vulnerability

Prefer the repository's private **GitHub Security Advisory / Report a vulnerability** workflow when available. If that workflow is not available, open a minimal public issue asking for a private reporting channel **without publishing exploit details, credentials, tokens, private file paths or proof-of-concept payloads**.

Please include the affected version, Windows version, whether the issue affects the Core or an external AI runtime, and the minimum reproduction steps needed to confirm the problem.

## Scope notes

Unum Sunt Sprite Studio deliberately separates the GPL-covered Core from external AI runtimes and model weights. Reports concerning WanGP, Krea, PyTorch, Miniconda or model behavior may need to be coordinated with the corresponding upstream project when the vulnerability is outside Sprite Studio's own code.

The application must never persist Hugging Face access tokens or other credentials in project files, logs or runtime state. Managed archive extraction is constrained against path traversal, absolute-path and symlink attacks. External/adopted runtimes must remain protected from destructive managed cleanup operations.
