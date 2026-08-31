# R5c3c — Managed Animate Settings Template Hotfix

## Cause
The managed runtime could be healthy while the video bridge still pointed to a stale/generic `wangp_settings.json`.
WanGP CLI requires an official settings payload containing `model_type`; without it the CLI exits before generation.

## Fix
- bundle a canonical Wan2.2 Animate settings template under `assets/runtime/wan_animate_settings_template.json`
- force managed video bridge configurations to use that template
- preserve the dedicated `wangp_env` Python binding
- require `model_type=animate` and `model_filename` in the managed template
- expose template validity in Runtime Health Check
- reject generic/non-official settings templates in the standard managed WanGP bridge health check

## Migration
No Miniconda, PyTorch, WanGP or Animate redownload is required. Opening the Runtime Manager / health check or starting the managed-runtime sync rewrites the bridge configuration to the bundled template.
