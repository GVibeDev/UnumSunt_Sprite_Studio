# R5c3b — Runtime Bridge Binding Hotfix

## Root cause
R5c3 correctly created a dedicated `wangp_env` with Python 3.11, but the Generate workspace could later restore an older runtime configuration from application/project state and overwrite `local_wangp.json`. On machines where current Miniconda base ships with Python 3.14, this could make the bridge launch:

`<runtime>/miniconda/python.exe`

instead of the intended:

`<runtime>/wangp_env/python.exe`

The base Miniconda interpreter does not own the WanGP PyTorch stack, producing `ModuleNotFoundError: No module named 'torch'`.

## Fixes
- `local_wangp.json` is now the single source of truth for the video bridge; runtime paths are no longer duplicated into app/project snapshots.
- managed runtime state can repair stale R5c3 bridge paths at startup without reinstalling models/runtime.
- Runtime Manager synchronizes video and image bridge configs after a successful health check/install.
- bridge binding is constrained to `<runtime>/wangp_env/python.exe`.
- local WanGP health check now verifies that PyTorch is importable; CUDA availability is reported as a warning there and remains governed by the R5c2 preflight/runtime health contract.
- runtime bridge orchestration lives in `RuntimeBridgeController`, keeping `MainWindow` at 79 methods.

## Existing installations
No redownload of Wan Animate or Miniconda is required when the existing managed runtime is healthy. Starting R5c3b or opening `File → Gestione runtime AI…` is enough to resynchronize the bridge.
