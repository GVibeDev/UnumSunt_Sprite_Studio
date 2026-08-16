# R5c3 — Automated AI Runtime Installer / Model Manager

## Scope
R5c3 turns the validated R5c2 preflight into an installation, repair and health-management layer for the Windows local-AI runtime.

The Sprite Studio Core remains self-contained. AI components are installed only under user-selected runtime/model roots; the installer does not replace the system Python and does not add its private Python to the global PATH.

## Automated runtime contract
- Private Miniconda installation (`JustMe`, no Python registration, no PATH modification)
- Private prefix environment with Python 3.11.14
- PyTorch 2.10.0 / torchvision 0.25.0 / torchaudio 2.10.0 from the cu130 wheel index
- WanGP source tree and `requirements.txt`
- Hugging Face Hub client
- Wan 2.2 Animate 14B primary Quanto BF16 INT8 checkpoint
- Krea 2 Turbo primary checkpoint after explicit gated-access/license acknowledgement
- Automatic Sprite Studio video/image bridge configuration

## Safety and integrity
- The validated R5c2 preflight is run again before downloads.
- CUDA/driver, storage and path errors can block installation.
- GPU model, VRAM and physical RAM remain diagnostic only.
- Hugging Face tokens are transient and are never written into Sprite Studio install state.
- The Animate primary checkpoint has a frozen byte size and SHA-256 check.
- Miniconda Authenticode signature is checked on Windows before silent execution.
- Partial direct downloads use `.part` files and HTTP Range resume when supported.
- Repair/update preserves existing WanGP settings/configuration when possible.

## CUDA Toolkit note
The private PyTorch environment uses cu130 and the required health gate is `torch.cuda.is_available()`. A system CUDA Toolkit / `nvcc` installation is detected by Health Check but is **optional/non-blocking in R5c3**. This avoids changing a system-wide CUDA installation unnecessarily. If a selected WanGP accelerator/kernel later requires a local toolkit, the Health Check makes that visible and the requirement can be promoted after real-machine tests.

## Model storage
R5c3 freezes the primary Wan Animate checkpoint at 17,933,520,197 bytes. The install plan also reserves additional model space because WanGP may acquire shared encoders, VAEs or other model-specific assets on demand. Krea 2 is gated and may likewise require upstream/shared assets depending on the active WanGP profile.

## UI
`File → Gestione runtime AI…`

Available actions:
- Preflight
- Health Check
- Install selected components
- Repair/update runtime
- Remove Animate
- Remove Krea 2
- Cancel current download between cancellable operations

## CLI
The standalone executable exposes:

```text
--runtime-health <report.json>
--runtime-install <state.json>
--runtime-root <path>
--model-root <path>
--accept-anaconda-tos
--accept-krea-license
--skip-runtime
--skip-animate
--skip-krea2
--repair-runtime
```

For Krea 2, `HF_TOKEN` is read from the process environment and is deliberately not accepted as a command-line parameter.

## Validation gate
R5c3 cannot be declared valid from Linux/container tests alone. Windows validation must include at least:
1. preflight on a CUDA-compatible NVIDIA machine;
2. private Miniconda + Python 3.11 creation;
3. PyTorch CUDA health check;
4. WanGP source/requirements installation;
5. at least the Animate checkpoint download and hash verification;
6. bridge health from Sprite Studio;
7. a real WanGP generation through Sprite Studio.

Krea 2 additionally requires approved Hugging Face gated access and explicit license/AUP acceptance.
