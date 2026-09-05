# P2-Ga — Validation Hotfix

Required baseline: `UnumSunt_Sprite_Studio_P2G_CANDIDATE_SOURCE.zip`

This candidate addresses the three issues reported during the P2-G Windows validation pass. P2-G is **not** considered validated until this hotfix passes the manual gate below.

## Fixes and completion work

### 1. Clean-up — Show Alpha on Checkerboard
The checkbox was connected directly to a preview method whose only parameter is keyword-only. Qt emits the checkbox boolean positionally, producing a runtime exception. The signal is now adapted explicitly and the preview refresh remains argument-safe.

### 2. Align — Onion on the shared CREATE canvas
P2-G re-housed the legacy Alignment onion controls, but those controls still targeted the specialized AlignmentCanvas while the persistent CREATE `Canvas` uses the P2-F shared onion state. The hotfix bridges the existing Alignment controls to the shared canvas without replacing the legacy Alignment engine:

- checkbox ON -> shared onion mode `Previous`;
- checkbox OFF -> shared onion mode `Off`;
- opacity slider -> shared onion opacity;
- entering Align synchronizes the current Alignment controls into the shared canvas.

### 3. Character Set — real preview and composite export
The P2-G Character Set layer stack was metadata-only; its UI explicitly deferred compositing to a later milestone. P2-Ga completes the user-visible path without destructive frame rewriting.

- `Preview Composite` renders the selected Direction on the persistent shared canvas.
- Export Studio now exposes `Character Set composite (R2 + visible export layers)`.
- Single-image layer assets are reused across every R2 base frame.
- Sequence assets must have exactly the same frame count as the active R2 sequence.
- Preview uses enabled + visible assignments.
- Export additionally requires the layer `Include in Character Set composite export` flag.
- Layer opacity and X/Y offsets are applied during composition.
- Assigned missing/invalid manifests and incompatible sequences are blocking errors. The application does not guess, cycle, truncate or silently repair inconsistent data.

## Automated gate

- `python -m compileall -q app` -> PASS
- `python -m pytest -q` -> 477 passed, 0 failed, 63 skipped, 36 subtests passed
- `python -m unittest discover -s tests -q` -> 540 tests OK, 63 skipped

The skipped tests are Qt/PySide6-dependent in the current build environment. Manual Windows validation remains required.

## Manual Windows validation

1. Clean-up: toggle `Show Alpha on Checkerboard` both ways, continue painting, then Undo/Redo. No exception or loss of brush responsiveness.
2. Align: with at least two frames, enable `Show Previous Frame`, change onion opacity and inspect both `Canvas` and `Current Workspace`. The shared Canvas must show the previous frame; disabling it must remove the onion.
3. Character Set: activate the intended Direction, add an equipment layer, assign a raster asset, use `Preview Composite`, then change visibility/opacity/offset and preview again.
4. Export: choose `Character Set composite (R2 + visible export layers)` and export a spritesheet. The assigned layer must appear. Unchecking `Include in Character Set composite export` must exclude it from export while leaving non-destructive preview behaviour available.
5. Error contract: if a sequence asset has a different number of frames from the active R2 sequence, preview/export must stop with a readable error rather than cycling or truncating frames.
6. Regression: switch repeatedly among CREATE routes and between `Canvas` / `Current Workspace`; current frame, selection and P2-F shared canvas state must remain coherent.
