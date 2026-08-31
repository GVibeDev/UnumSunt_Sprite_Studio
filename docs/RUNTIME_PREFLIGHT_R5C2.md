# R5c2 — CUDA / Storage / Paths Preflight

## Purpose
R5c2 is the compatibility and capacity gate that will be called by the R5c3 automated AI runtime installer. It performs no installation and makes no system changes.

## Policy frozen by product decision
- GPU model: diagnostic only; never blocks R5c2.
- VRAM: diagnostic only; never blocks R5c2.
- RAM: diagnostic only; never blocks R5c2.
- CUDA/driver compatibility: blocking.
- Windows x64: blocking for the current Windows distribution line.
- invalid/unwritable paths: blocking.
- insufficient disk space: blocking.

This deliberately allows validation on machines such as RTX 3070 8 GB / 16 GB system RAM when the installed NVIDIA driver satisfies the CUDA contract.

## Current WanGP runtime contract
The R5c2 plan uses the currently selected WanGP Windows profile:
- Python 3.11.14
- PyTorch 2.10.0
- PyTorch CUDA wheel family: CUDA 13.0
- WanGP toolkit recommendation: CUDA 13.1

The preflight does **not** require a locally installed CUDA Toolkit merely to pass. It reads the maximum CUDA compatibility exposed by the installed NVIDIA driver through `nvidia-smi` and requires `CUDA Version >= 13.0`.

R5c3 will own toolkit/runtime installation and exact package hashes.

## Storage model
The plan is data-driven in `assets/runtime/runtime_install_plan.json`.

Current provisional planning values:
- Miniconda/bootstrap: 1.5 GiB installed + 0.5 GiB temporary
- WanGP/Python/PyTorch/CUDA dependencies: 20 GiB installed + 4 GiB temporary
- Wan Animate package: 32 GiB installed + 4 GiB temporary — provisional until the exact R5c3 model variant is frozen
- Krea 2 Turbo checkpoint: 26.3 GiB installed + 2 GiB temporary
- AI workspace/output reserve: 20 GiB
- safety margin: 10%

With runtime and models on the same drive this currently reserves about 121 GiB. When they are on separate drives the preflight evaluates each drive independently.

## Entry points
### GUI
`File → Verifica runtime AI…`

The dialog lets the user choose separate runtime and model roots, displays the component plan, executes the check and saves a JSON report.

### CLI / future installer
```text
UnumSuntSpriteStudio.exe --runtime-preflight report.json \
  --runtime-root C:\AI\UnumSunt\runtime \
  --model-root D:\AI\UnumSunt\models
```

Exit codes:
- `0` = READY or WARNING
- `2` = BLOCKED

## Result contract
Every report includes:
- overall `READY / WARNING / BLOCKED`
- detected NVIDIA GPUs, driver versions and VRAM as diagnostics
- driver-reported CUDA compatibility
- RAM as diagnostics
- path syntax/writability checks
- per-drive free/required space
- component size plan
- existing WanGP config detection
- explicit notes that R5c2 performs no installation
