# Unum Sunt Sprite Studio R5c6a — Cumulative Hotfix Test 2

This package is cumulative and is intended to be extracted over the R5c6a repository root.
It includes the previously issued Image Gen memory-profile hotfix plus the Production Presets save/refresh crash fix.

## Fix 1 — Image Gen memory controls
- WanGP Image memory profile selector (Auto / 1–5).
- Optional reserved RAM max value.
- Managed CLI arguments for `--profile` and `--perc-reserved-mem-max`.
- More useful CUDA OOM diagnostic.

## Fix 2 — Production Presets refresh crash
Observed exception:

`QListWidget.findItems(str, int)` / expected `Qt.MatchFlag`.

Root cause: `refresh()` called `findItems(current, 0)`, which is rejected by current PySide6 bindings.

Fix: the list is populated from the exact `names` sequence, so the selected preset is restored with
`setCurrentRow(names.index(current))`. This removes the binding-sensitive flag call entirely.

## Status
TEST HOTFIX only. Do not promote R5c6a baseline until real-app validation is complete.
