# Migration R5c3d → R5c3e

## Scope
R5c3e addresses the two blockers discovered during the first main-PC rollout of R5c3d.

### 1. Build/test GPU guard scope
The R5c3d GPU/PyTorch guard was correctly required for real local AI runtimes, but it was also making PyTorch mandatory for development/mock WanGP fixtures used by the standalone regression suite. That caused both `build_windows_standalone.bat` and `build_exe_windows.bat` to stop before PyInstaller.

R5c3e keeps the GPU capability guard mandatory for real runtime bindings (`strict_python_311=True`) while development/mock providers (`strict_python_311=False`) remain independent of PyTorch. The Core `.build-venv` therefore does not need Torch.

### 2. Existing Runtime Adoption
A runtime no longer has to use Sprite Studio's managed folder layout.

The Runtime Manager can now:
- detect the current bridge configuration;
- detect conservative legacy layouts such as `C:\AI\envs\WanGP` + `C:\AI\WanGP_Standalone`;
- manually adopt an existing `python.exe`, `wgp.py` and models directory;
- validate the external runtime before adoption;
- persist explicit external paths;
- reuse the external runtime without copying, moving, renaming, repairing or deleting its files.

External runtimes are marked `ownership=external`. Managed repair/update/model-removal controls are disabled while an external runtime is active.

## Non-goals
- No Pillow deprecation cleanup in this patch.
- No automatic migration or renaming of old runtime folders.
- No re-download of already existing model files.
