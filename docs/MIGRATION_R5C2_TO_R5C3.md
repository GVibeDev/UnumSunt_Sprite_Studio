# Migration R5c2 → R5c3

R5c2 remains the validated preflight foundation. R5c3 adds the execution layer that installs, repairs, checks and removes selected local-AI components only after that preflight permits the operation.

No minimum GPU model, VRAM or RAM threshold is introduced. The runtime continues to use CUDA compatibility, path validity and available storage as the blocking hardware/environment gates.

New persistent state: `%LOCALAPPDATA%/UnumSuntSpriteStudio/runtime_install_state.json`. Hugging Face credentials are explicitly excluded from persistence.

New UI entry: `File → Gestione runtime AI…`.
