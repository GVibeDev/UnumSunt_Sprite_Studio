# R5c3e — Existing Runtime Adoption

R5c3e separates **managed** and **external/adopted** AI runtimes.

## Managed runtime
Created by Sprite Studio under its selected runtime/model roots. Sprite Studio may install, repair, update and remove managed components.

## External runtime
An existing WanGP installation created manually or by an earlier Sprite Studio/WanGP setup. Sprite Studio stores only its paths and uses it in place. It does not rename, move, repair, update or delete the external tree.

## Runtime Manager
Use:

1. `File → Gestione runtime AI…`
2. `Rileva installazioni esistenti`
3. choose a candidate and press `Adotta selezionato`

If automatic detection does not find the installation, use `Adotta manualmente…` and select:
- the WanGP Python 3.11 `python.exe`;
- WanGP `wgp.py`;
- the existing model/checkpoint directory.

The runtime is adopted only after the same real WanGP health contract passes, including Python 3.11, PyTorch/CUDA and GPU compute-capability compatibility.
