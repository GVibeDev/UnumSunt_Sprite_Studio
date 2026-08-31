# R5c6b — Validated cumulative hotfix baseline

Validated by the author on 16 August 2026.

R5c6b is the operational baseline obtained from R5c6a plus the validated cumulative hotfixes:

- Image Gen WanGP memory controls: selectable memory profile, reserved-RAM cap, persisted image-runtime settings and clearer CUDA OOM diagnostics.
- Production Presets refresh/save crash fix: removes the invalid `QListWidget.findItems(str, int)` call and selects the newly saved preset by row.

This document supersedes the temporary TEST_ONLY hotfix notes/manifests for baseline purposes. Runtime, models and user projects remain external to this source patch.
