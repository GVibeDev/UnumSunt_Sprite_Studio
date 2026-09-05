# Unum Sunt Sprite Studio — Phase 2 Canonical CREATE Workspace Contract

Status: **VALIDATED ROADMAP CONTRACT — 2026-09-01**

This document freezes the functional hierarchy and input contract for Phase 2. It does not freeze final pixel geometry, the final CREATE tool list, keyboard shortcuts, mouse-wheel behavior while a tool is active, persistence of the selected tool, or final numeric panel dimensions.

## 1. Product hierarchy

The application hierarchy is:

**Application Menu → Generate / Create / Manage → Project Context → Contextual Toolbar → Three-column Workspace**

CREATE is canvas-centered. The canvas is the dominant production surface, not a preview panel.

## 2. Application menu

Keep the traditional application menu (`File`, `Edit`, etc.) above the workstation. General actions remain centralized here and must not be reimplemented independently inside CREATE.

## 3. Persistent macro navigation

`GENERATE`, `CREATE`, and `MANAGE` remain the three primary application environments introduced in Phase 1. CREATE must be visibly identifiable as active when selected. Macro navigation remains available through the primary workstation controls and through the neutral canvas context menu.

The sketch's semicircular geometry is compositional guidance only. The functional hierarchy is frozen; final control geometry is not.

## 4. Project context / breadcrumb

The upper-right context area is informational/orientational rather than a second global menu. It must expose the real active production hierarchy supported by the data model.

Canonical direction for the current model:

**CHARACTER / SUBJECT → ANIMATION → DIRECTION → current SPRITE / ASSET / FRAME when available**

The concrete labels, clickability and breadcrumb controls will be implemented against actual ProjectStore / ProjectSession data rather than invented placeholders.

## 5. Contextual toolbar

The horizontal toolbar changes with the macro environment. In CREATE it contains high-frequency workspace actions and commands relevant to the current production context.

The canonical tool palette belongs to **Tools & Options** on the left. If a toolbar shortcut activates a tool in the future, it must activate the same `tool_id` through the same controller; it must not create a second tool implementation.

## 6. CREATE three-column workspace

### Left — Tools & Options

Contains available tools, active-tool options and operation-specific properties. Content is contextual. If no tool is active, the panel must not pretend that a tool is selected.

### Center — Canvas / Production

The primary area. It receives the majority of resizable space and remains useful when the application window becomes smaller. Users navigate, edit, inspect and produce directly here.

### Right — Configurations & Output

Contains result/output configuration rather than direct canvas manipulation tools.

Conceptual separation:

- left = **with what / how I intervene**
- center = **what I am working on**
- right = **result configuration / output**

Existing controls must be audited before relocation. Phase 2 must not invent new production functions simply to fill panels.

## 7. Stacked/tabbed panel rule — frozen after Phase 1

Do **not** solve dense workspaces by keeping every field visible in one vertical panel.

The current Alignment UI demonstrates the failure mode: in full-screen layouts, selected/context fields can be compressed in order to fit the complete Alignment control set.

Phase 2 therefore adopts a **same-sector stacked/tabbed presentation rule**:

- logically related control groups occupy tabs/pages in the same left or right panel sector;
- only the active group/page needs to be visible at one time;
- secondary groups must not force primary/current-context fields below a useful size;
- long tool/configuration sets should use local tabs, stacked pages, expandable/cascading groups or an equivalent same-sector navigation pattern;
- do not create floating windows merely to escape panel pressure;
- do not duplicate a control on multiple pages to make it easier to reach;
- the shared canvas keeps layout priority over inactive/secondary control pages.

The exact tab labels and grouping for Alignment, Clean-up, Export and the other legacy workspaces will be decided only after the P2-G control audit.

## 8. Neutral canvas input contract

When no operational tool is active:

- **LMB drag → PAN**
- an LMB click without a drag does not move or mutate content
- **RMB → general canvas context menu**

PAN IS NOT A TOOL. It is the natural neutral state of the canvas.

## 9. General canvas context menu

Neutral RMB provides at least:

- File
- Edit
- Generate
- Create
- Manage

File/Edit entries reuse or coordinate with the same application actions as the main menu. Opening the context menu must not alter content, pan, zoom, selection, tool activation or project state.

## 10. Active tool input contract

**TOOL ACTIVE > DEFAULT CANVAS INPUT**

When a tool is active, mouse input is routed to that tool through the central input controller. There is no accidental fallback to the neutral RMB context menu merely because a tool chooses not to use a specific mouse button.

Conceptually:

```text
NO TOOL
  LMB drag -> PAN
  RMB      -> GENERAL CONTEXT MENU

TOOL ACTIVE
  mouse event -> active tool contract
  handled     -> tool action
  unhandled   -> no action unless the tool explicitly delegates
```

Disabling the tool restores neutral behavior immediately.

## 11. Central input architecture

Avoid competing canvas listeners owned independently by each tool.

Minimum logical states:

- `CANVAS_NEUTRAL`
- `TOOL_ACTIVE`

Event routing:

```text
mouse event
  -> CanvasInputController
  -> active tool?
       yes -> active tool contract
       no  -> neutral canvas behavior
```

Press → move → release belongs to one interaction session. If a tool is disabled, the project/direction changes, or the canvas context becomes invalid during that session, the controller must cancel the session and release any mouse capture explicitly.

The controller is reusable by any application surface that needs the same canvas contract; Generate and Manage are not required to use a canvas simply for architectural symmetry.

## 12. Shared canvas layers & overlays — P2-E

The persistent CREATE canvas owns a non-destructive visual scene. The scene is a rendering/runtime concern, not a second project document.

The frozen P2-E layer order is:

1. neutral canvas background;
2. transparency checkerboard inside the active document geometry;
3. previous/next onion raster layers;
4. current frame raster layer;
5. grid;
6. guides;
7. selection overlay;
8. pivot overlay.

`CanvasVisualState` stores document geometry, layer metadata and overlay metadata only. `SharedCreateCanvas` owns the corresponding `QImage` render buffers. Neither object duplicates ProjectStore JSON, pipeline state or ProjectState identity data.

Raster layers have explicit semantic roles, visibility and opacity. Onion-skin is therefore a normal render layer with bounded opacity rather than a special destructive image operation. The current frame paints above onion layers.

Selections, guides, grid and pivot are overlays only: displaying, hiding or changing them must not mutate the underlying frame pixels.

The shared canvas exposes stable canvas↔view coordinate conversion using the same pan/zoom transform used for rendering. This coordinate contract is intended for future tools, while mouse-wheel behavior remains intentionally unfrozen.

P2-E does not implement the Paint Engine, Mesh, Rig or Animation systems and does not force legacy CREATE workspaces onto the shared canvas before P2-G.

## 13. Workspace/view persistence

When compatible with the current project context, the architecture must be capable of retaining:

- project / character / animation / direction / sprite context;
- pan;
- zoom;
- panel sizes;
- collapsed panel state;
- current local panel page/tab.

Persistence of an active operational tool is intentionally **not frozen**. The default Phase 2 foundation treats tool selection as transient until explicitly decided otherwise.

## 14. Responsibility boundaries

- application menu → global app operations
- Generate/Create/Manage → environment selection
- project context → orientation/status
- contextual toolbar → workspace commands
- left panel → tools and tool options
- canvas → direct interaction and production
- right panel → result configuration and output

## 15. Layout requirements

The canvas remains visually dominant. Side panels may be resizable/collapsible but must not compress the center to an unusable area. Under constrained space, preserve the canvas and essential controls first, then collapse/reduce secondary panel content.

## 16. Phase 2 acceptance contract

Phase 2 UI foundation is complete only when:

- Generate/Create/Manage remain present and CREATE is visibly active;
- the application menu remains present;
- project context exposes at least Subject/Character, Animation and Direction, plus asset/frame when available;
- CREATE has contextual toolbar + Tools & Options / Canvas / Configurations & Output;
- the canvas is the dominant resizable area;
- the shared canvas supports deterministic current-frame/onion raster composition without storing pixel payloads in ProjectState;
- transparency, grid, guides, selection and pivot are non-destructive overlays;
- canvas/view coordinate conversion uses the same pan/zoom transform as rendering;
- dense control collections use same-sector stacked/tabbed/cascading presentation instead of squeezing all fields simultaneously;
- neutral LMB-drag always pans;
- neutral RMB always opens the general canvas context menu;
- the neutral context menu exposes File/Edit and Generate/Create/Manage without mutating project/canvas state;
- an active tool receives its declared mouse inputs through the central dispatcher;
- deactivation immediately restores neutral behavior;
- cancelled tools/interactions leave no captured/listening mouse state;
- macro-environment changes do not cause accidental work loss;
- existing controls are audited and relocated without arbitrary duplication or replacement.

## 17. Intentionally not frozen

Do not decide implicitly during implementation:

- final CREATE tool list;
- complete Configurations & Output contents;
- final macro-navigation geometry;
- keyboard shortcuts;
- whether Escape deactivates a tool;
- mouse-wheel behavior while a tool is active;
- active-tool persistence between environments/sessions;
- final numeric panel dimensions;
- exact Alignment/Clean-up/Export local tab names before audit.

## 18. Phase 2 implementation sequence

1. **P2-A — ProjectState + View/Tool State Foundation — VALIDATED**
2. **P2-B — CREATE Workspace Structural Shell — VALIDATED**
3. **P2-C — Persistent Shared Canvas + CanvasInputController — VALIDATED**
4. **P2-D — General Canvas Context Menu — VALIDATED**
5. **P2-E — Canvas Layers & Overlays — VALIDATED 2026-09-05**
6. **P2-F — Frame & Project Context — VALIDATED 2026-09-05**
7. **P2-G — Existing CREATE Tools Rehousing + control audit / local panel tabs — IMPLEMENTATION CANDIDATE**
8. **P2-H — Persistence & Hardening**

Paint Engine, Mesh, Rig and Animation remain later phases. Phase 2 builds the stable workstation surface they will use.
