# Migration R5c1c → R5c2

## R5c2 — CUDA / Storage / Paths Preflight

R5c2 introduces a non-destructive preflight layer for the future automated local-AI installer.
It does **not** install or modify NVIDIA drivers, CUDA, Python, Miniconda, PyTorch, WanGP or models.

### Frozen policy
- no minimum GPU model is enforced;
- no minimum VRAM is enforced;
- no minimum system RAM is enforced;
- GPU model, VRAM and RAM are recorded only as diagnostics;
- blocking compatibility is based on Windows x64, CUDA capability exposed by the NVIDIA driver, valid/writable paths and sufficient free disk space.

### CUDA contract
The current WanGP profile targets:
- Python 3.11.14
- PyTorch 2.10.0
- CUDA driver capability >= 13.0
- recommended WanGP CUDA toolkit 13.1

The exact packages and hashes remain a R5c3 responsibility.

### Runtime plan
`assets/runtime/runtime_install_plan.json` contains component size estimates and can be frozen/updated by R5c3 without rewriting the preflight engine.

### User entry points
- `File → Verifica runtime AI…`
- frozen/source CLI: `--runtime-preflight <report.json>`
- optional CLI overrides: `--runtime-root <path>` and `--model-root <path>`

### Result
The report returns one of:
- `READY`
- `WARNING`
- `BLOCKED`

and can be saved as JSON for the installer/runtime manager.
