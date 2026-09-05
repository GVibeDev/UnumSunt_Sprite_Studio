# P2-E — Canvas Layers & Overlays

Status: **RECONCILED implementation candidate pending Windows/manual validation**.

P2-E turns the persistent shared CREATE canvas from a neutral input surface into a real layered production surface without moving the validated legacy CREATE tools before P2-G. The September reconciliation keeps the P2-F frame/project context intact and removes the duplicate canvas implementation that had drifted away from the active runtime.

## Ownership model

The rendering boundary is deliberately split:

```text
CreateWorkspaceState
  └─ CanvasVisualState
       ├─ document geometry
       ├─ CanvasLayerStack metadata
       └─ CanvasOverlayState metadata

SharedCreateCanvas
  ├─ CanvasImageLayerCache (RGBA presentation copies only)
  └─ QImage render buffers
```

`CanvasVisualState` contains no decoded image arrays, project JSON, ProjectStore payload or pipeline state. `ProjectState` remains identity/context state only.

The renderer cache is **presentation-only** and **not an edit buffer**. It is never project persistence and never replaces CleanupStudio, Alignment, ProjectStore or any future Paint Engine document owner.

## Raster layer order

The semantic roles remain:

- `ONION_PREVIOUS`
- `ONION_NEXT`
- `CURRENT_FRAME`

The P2-F UI exposes one explicit onion neighbour at a time (`Off / Previous / Next`). The selected neighbour is represented with the corresponding semantic onion role and is painted behind the current frame. Onion visibility and opacity are transient presentation state.

## Overlay order

The P2-E visual order remains:

```text
canvas background
transparency checkerboard
onion frame when enabled
current frame
grid
guides / ground reference
selection
pivot
```

Grid, guides, ground reference, selection and pivot are visual overlays only. Their APIs update transient canvas metadata and never modify frame pixels.

## Image geometry and coordinate conversion

The current RGBA frame establishes the logical document width and height. Rendering, overlays and future tools share the same image geometry and pan/zoom transform.

The active canvas exposes `image_to_canvas()` and `canvas_to_image()` so future tools can translate between **image coordinates** and widget/canvas coordinates without inventing independent transforms.

The P2-E connectivity hotfix later froze neutral mouse-wheel zoom. Tool-specific wheel behavior remains intentionally open; an active tool suppresses neutral wheel fallback until that tool explicitly defines its own behavior.

## P2-F integration

P2-F owns the user-facing onion policy and persistent frame context:

- `Off`
- `Previous`
- `Next`

The canvas does not guess an adjacent frame by itself. MainWindow resolves the requested frame through the existing decode/chroma/override path and supplies the resulting RGBA presentation layer. Boundary cases therefore resolve to no onion layer rather than implicit wrapping.

The persistent frame strip, current-frame identity and production selection remain separate from the render cache. No source pixel payload is stored in `ProjectState`.

## Compatibility boundary

P2-E/P2-F do not move Import, Extract, Select, Clean-up, Alignment, Character Set or Export off their validated legacy workspaces. The shared canvas and `Current Workspace` remain two local pages inside the CREATE production sector until P2-G audits and re-houses the existing controls.

No Paint Engine, Mesh, Rig or Animation logic is introduced here.

## Manual validation

On Windows/PySide6:

1. run the complete automated suite with PySide6 available;
2. launch Sprite Studio and verify no regression in GENERATE / CREATE / MANAGE;
3. verify `Current Workspace` remains the default CREATE transition page;
4. switch to `Canvas`, load a decoded frame and verify the transparency background stays behind it;
5. select Onion `Previous` and `Next` and verify the correct processed neighbour is shown behind the current frame;
6. verify boundary frames show no onion layer;
7. toggle/present grid, guides, selection and pivot and verify they track the same image coordinates through pan/zoom;
8. verify `image_to_canvas()` → `canvas_to_image()` round-trips within floating-point tolerance;
9. verify source/frame changes clear stale presentation layers without changing tool selection or ProjectStore data;
10. switch CREATE route/project context and verify no pointer interaction remains captured.

P2-E reconciliation is valid only when the Windows/PySide6 suite passes and the layered scene introduces no regression to the validated P2-D input/menu contract or the P2-F frame/project context.
