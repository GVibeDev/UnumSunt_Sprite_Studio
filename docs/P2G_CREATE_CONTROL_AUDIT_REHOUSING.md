# P2-G — Existing CREATE Tools Rehousing + Control Audit

Status: **IMPLEMENTATION CANDIDATE — pending Windows/manual validation**  
Input baseline: **validated P2-E/P2-F reconciled source — 2026-09-05**

## Purpose

P2-G performs the control audit deferred by P2-B and moves the existing CREATE controls into the persistent Phase 2 side sectors without creating replacement implementations.

The milestone is deliberately conservative:

- the same existing Qt control widgets are re-parented;
- their signal/slot connections and engine ownership stay unchanged;
- the validated specialized production surfaces remain available in `Current Workspace`;
- the shared CREATE canvas remains the persistent `Canvas` page;
- no ProjectStore schema, frame-selection contract, chroma algorithm, clean-up engine, alignment engine or export engine is rewritten.

This is a UI-ownership migration, not a production-engine rewrite.

## Rehousing rule

The persistent CREATE hierarchy remains:

- left: `Source / Tools / Options`;
- center: `Canvas / Current Workspace`;
- right: `Configurations / Output`;
- bottom: persistent P2-F frame strip.

Each left/right tab contains one route-aware stacked page. Selecting a CREATE route switches all side-sector stacks to the matching route while preserving the registered production widget instance.

Controls are not copied. The audited `QGroupBox` instance is removed from its legacy control column by Qt re-parenting and inserted into the matching persistent side-sector page.

If an audited title is missing or resolves more than once on the real registered workspace, registration fails with a `P2-G control audit mismatch` instead of guessing.

## Audited placement

| CREATE route | Source | Tools | Options | Configurations | Output | Central content retained |
| --- | --- | --- | --- | --- | --- | --- |
| Import | Source | Grid slicer | Irregular Atlas | Decompose | Existing Pipeline; WAN Reference Sheet Builder | spritesheet preview + frame list |
| Extract | Video | Background Extraction | Additional Background Colors; Structural Refinement; Alpha / Chroma Profiles; Selected Frames | — | R1 Export | five preview tabs + legacy timeline |
| Select | — | Range and Profile | — | — | — | selected-frame player, analysis summary/table and analysis/apply actions |
| Clean-up | — | Clean-up alpha; Pixel painter | Selections and Propagation | — | — | Clean-up canvas, frame navigation/list |
| Align | — | Current Frame Alignment | View and Onion Skin | Output Geometry and Global Anchor; Alignment Profiles | Animation and Export | Alignment canvas, frame navigation/list |
| Character Set | — | Subject Logical Layers | — | Layer Assets by Direction | — | character/direction context + coverage table |
| Export | — | — | — | Export Profiles; Source and Destination | Outputs to Generate; Final Resolution and Background | export introduction + final export action |

## Decisions from the audit

### 1. Alignment compression is removed structurally

The former single right-side Alignment column contained geometry, profiles, current-frame alignment, view/onion and animation/export simultaneously. P2-G splits those existing groups between four persistent pages so inactive groups no longer determine the usable height of the active current-frame controls.

### 2. Clean-up remains a specialized production surface

`CleanupCanvas` is not replaced in P2-G. Paint and selection controls move left, while the validated Clean-up canvas remains in `Current Workspace`. Adapting painter input directly to `SharedCreateCanvas` would be a tool-engine migration and is outside this milestone.

### 3. Alignment remains a specialized production surface

The same rule applies to `AlignmentCanvas`. P2-G fixes control ownership/layout pressure without rewriting pivot/drag behavior onto the shared input controller.

### 4. Extract background controls are split rather than moved as one giant group

The nested `Additional Background Colors`, `Structural Refinement` and `Alpha / Chroma Profiles` groups are detached from `Background Extraction` and moved to `Options`. This is the concrete application of the same-sector stacked/tabbed rule frozen in the Phase 2 contract.

### 5. Source opening remains centralized

The CREATE `Source` tab continues to reuse the same `QAction` objects as the application File menu. The legacy Import workspace's independent `Open Spritesheet…` button is hidden after rehousing so the visible Phase 2 surface does not present two implementations of the same source-opening command.

### 6. Redundant Extract route-navigation buttons are removed from the visible UI

The old `Go to …` buttons are hidden because CREATE route navigation is now permanently available in the contextual route toolbar. Their removal changes no engine behavior.

### 7. Legacy control columns collapse only where they are genuinely obsolete

After their audited groups move out, the old control columns are hidden for Import, Extract, Clean-up and Align. Select keeps its results table/actions in the existing right production column. Character Set and Export retain central result/action content that is not side-panel configuration.

## Runtime contract

`app/create_control_rehousing.py` is the single declarative placement registry.

Each plan declares:

- route id;
- source file used by the audit contract;
- expected production widget class when one exists;
- exact existing group title;
- destination section;
- preferred left/right local tab;
- whether the emptied legacy control column may collapse;
- explicitly redundant buttons to hide.

`CreateWorkspaceShell.register_widget()` performs the rehousing only for the real audited workspace type. Generic/dummy widgets used by shell tests are not forced through the production audit.

The Extraction workspace is historically an anonymous `QWidget`; P2-G gives it the explicit object name `extractionWorkspace` so the runtime can distinguish it from a test/dummy widget and enforce the exact audit.

## Persistence boundary

P2-G does not add a project migration.

The existing `CreateViewState` still owns:

- panel widths;
- collapsed state;
- selected left tab;
- selected right tab;
- production page.

Per-route restoration of the last local tab is intentionally deferred to P2-H. In P2-G a route change selects an audited useful default (`Tools`, `Source`, `Configurations` or `Output`) so the newly relevant controls do not open on an empty page.

## Automated acceptance

The implementation candidate must pass:

1. all seven CREATE routes covered by exactly one audit plan;
2. no duplicate audited control title inside one route;
3. every audited title present in its declared source file;
4. strict runtime mismatch detection for real audited workspaces;
5. existing shell route/widget identity preserved;
6. previous P2-A…P2-F contract/regression tests still green;
7. full Python compile gate;
8. full pytest/unittest regression gate.

Candidate result in the build environment used to prepare this patch:

- `python -m compileall -q app` — PASS;
- `PYTHONPATH=. python -m pytest -q` — **470 passed, 63 skipped, 36 subtests passed**.

Qt tests remain skipped in that environment when PySide6 is unavailable; Windows/manual validation is therefore mandatory before P2-G can be frozen.

## Windows/manual acceptance checklist

Validate from the attached reconciled baseline plus this P2-G patch:

1. application starts with no CREATE registration error;
2. Import: Source/Grid/Atlas/Decompose/Pipeline/Reference controls appear in the declared side tabs and the preview remains usable;
3. Extract: background controls are split between Tools/Options, R1 Export is on Output, previews and timeline still work;
4. Select: Range and Profile is on Tools; analysis table/player/actions still work;
5. Clean-up: alpha/painter controls are on Tools, propagation is on Options, painting/undo/redo/selection still work in Current Workspace;
6. Align: current-frame controls are no longer compressed by geometry/export groups; alignment, pivot, nudge, onion/view and export remain functional;
7. Character Set: logical layers appear left, direction asset assignment right, coverage remains central;
8. Export: profile/source configuration and final output options appear on the right, export completes normally;
9. changing CREATE routes switches side controls without recreating or resetting the route widget;
10. switching `Canvas` ↔ `Current Workspace` does not destroy side controls or frame context;
11. Source buttons still execute the same File-menu actions;
12. frame strip selection/onion behavior remains identical to validated P2-F.

## Out of scope

P2-G does not implement:

- Paint Engine on `SharedCreateCanvas`;
- Alignment tool input on `SharedCreateCanvas`;
- Mesh, Rig or Animation systems;
- final keyboard shortcuts;
- per-route local-tab persistence;
- final numeric side-panel dimensions;
- removal of the `Current Workspace` compatibility page.

Those boundaries prevent a UI migration from silently becoming a tool-engine rewrite.
