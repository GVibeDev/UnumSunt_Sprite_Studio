# P2-E Canvas Connectivity Hotfix

Status: **VALIDATED as part of the reconciled P2-E/P2-F source — 2026-09-05**.

## Reason

The first P2-E renderer could pan and display a frame supplied by MainWindow, but the canvas was still operationally isolated: selecting a CREATE route while the Canvas page was visible did not expose that route's controls, workflow routing could therefore appear to do nothing, and source-import commands were not surfaced inside the CREATE shell. Neutral wheel zoom was also missing.

## Closure

- Neutral mouse wheel zooms around the pointer and updates `CreateViewState`.
- Active tools suppress neutral wheel fallback until tool-specific wheel semantics are explicitly defined.
- The left CREATE sector gains a `Source` page whose buttons reuse the exact existing File-menu `QAction` objects for Open Video and Open Spritesheet.
- Supported local videos, spritesheets and sequence manifests can be dropped on the shared canvas; dispatch delegates to the existing validated import paths.
- `SpriteSheetWorkspace` exposes a public `open_sheet_path()` adapter and emits a source preview for the shared canvas; slicing/import logic remains unchanged.
- Explicit CREATE route navigation opens the route-control page, so Workflow Router and route buttons visibly lead to the requested controls.
- Successful video/spritesheet pipeline import returns to the persistent canvas so the loaded result is immediately visible.

No ProjectStore schema, ProjectSession contract, chroma implementation, spritesheet slicer, workflow definition or export engine is duplicated or replaced.
