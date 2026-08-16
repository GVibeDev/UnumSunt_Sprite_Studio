# R5c3b — Hugging Face Dependency Contract Hotfix

## Problem
R5c3 installed WanGP requirements correctly and then executed an unconditional:

`pip install --upgrade huggingface_hub`

On current package indexes this can install Hugging Face Hub 1.x. WanGP currently pins
`transformers==4.54.0`, whose runtime dependency contract requires
`huggingface-hub>=0.34.0,<1.0`. The result is an import-time crash before generation.

## Fix
- replace the unbounded upgrade with `huggingface_hub[hf_xet]>=0.34.0,<1.0`
- the same operation runs during Repair, so existing broken environments are downgraded automatically
- Runtime Health Check now imports both `transformers` and `huggingface_hub`
- `pip check` is exposed as a non-blocking diagnostic

## Recovery
Existing Miniconda, WanGP and downloaded model files do not need to be removed.
Run **Gestione runtime AI → Ripara / aggiorna runtime** to repair the Python package set.
