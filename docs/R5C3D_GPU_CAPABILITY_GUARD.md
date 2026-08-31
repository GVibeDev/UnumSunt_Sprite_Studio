# R5c3d — GPU Capability Guard & Runtime Compatibility Diagnostics

## Why this patch exists
The GTX 1050 field test reached the real WanGP generation path but PyTorch reported:

- GPU compute capability: `sm_61`
- architectures compiled into the installed PyTorch wheel: `sm_75 sm_80 sm_86 sm_90 sm_100 sm_120`

Driver-level CUDA compatibility alone was therefore insufficient to predict whether CUDA kernels could execute.

## Contract
R5c3d does **not** introduce a GPU model whitelist and does **not** introduce VRAM or RAM minimums.

It checks the actual contract between:

1. the installed managed PyTorch wheel;
2. `torch.cuda.get_arch_list()`;
3. the compute capability reported by the GPU to PyTorch.

A GPU is considered executable by the managed runtime only when its `sm_XX` architecture (or matching PTX `compute_XX`) is present in the installed wheel.

## Behaviour
- Runtime preflight: reports the PyTorch/GPU contract as READY/WARNING when a managed runtime already exists. It remains non-blocking for installation/repair.
- Runtime Manager Health Check: `torch.gpu_compatibility` is required for a READY runtime.
- Local WanGP Health Check: generation is NOT READY when the default CUDA device is incompatible with the installed PyTorch wheel.
- Generation validation therefore stops before launching WanGP instead of allowing a later `cudaErrorNoKernelImageForDevice` crash.

## Expected field tests
- GTX 1050 `sm_61`: runtime diagnostics must report incompatible and block local generation.
- RTX 3070 `sm_86`: expected compatible with the current cu130 PyTorch wheel.
- Main RTX machine: verify reported architecture, Health Check READY, Dry-run, then real Animate generation.
