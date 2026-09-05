# P2-C — Persistent Shared Canvas + CanvasInputController

Status: implementation candidate for validation.

## Purpose

P2-C introduces the first persistent CREATE canvas surface and freezes the pointer-input ownership contract before real image layers or editing tools are moved onto it.

The milestone does **not** rewrite the validated R5c8 CREATE tools. During the transition the central production sector contains two local pages occupying the **same sector**:

- `Canvas` — the new persistent shared canvas foundation;
- `Current Workspace` — the existing validated route widget.

They are never shown side-by-side. This follows the Phase 2 stacked/tabbed rule and prevents transitional UI from compressing the canvas or the current workspace. `Current Workspace` remains the default page in P2-C so existing functionality does not disappear while P2-G is still pending.

The same `SharedCreateCanvas` instance survives route changes and Generate/Create/Manage navigation. Pan/zoom live in `CreateViewState`; no project document copy is introduced.

## Central input controller

`CanvasInputController` is Qt-independent and owns pointer routing. Its only two logical modes are:

- `CANVAS_NEUTRAL`
- `TOOL_ACTIVE`

Neutral behavior frozen in P2-C:

```text
LMB press + drag beyond threshold -> PAN
LMB press + release without drag  -> no movement / no edit
RMB click                         -> general context-menu request
RMB drag                          -> no context-menu request
```

PAN remains canvas-neutral behavior, not a selectable tool.

## Tool priority

When a tool is active, all pointer events are delivered to its explicit `ToolInputTarget` contract. `IGNORED` never falls back accidentally to neutral canvas behavior. A tool must return `DELEGATE_NEUTRAL` explicitly on the new press if it wants that interaction to use the neutral contract.

This preserves:

```text
TOOL ACTIVE > DEFAULT CANVAS INPUT
```

## Interaction lifecycle

Press → move → release remains one interaction session. Tool switching or tool deactivation cancels an in-flight tool interaction and calls the tool cancellation hook. CREATE route/context changes cancel an in-flight interaction. Leaving CREATE also cancels the current interaction.

P2-C does not require `grabMouse()`. If later tools introduce explicit capture, the same cancellation boundary must release it.

Tool selection persistence is still not frozen. P2-C only guarantees that an interaction cannot leak across a route/environment/context boundary.

## Context menu boundary

Neutral RMB now emits `general_context_menu_requested` from `SharedCreateCanvas`, but P2-C deliberately **does not yet build the File/Edit/Generate/Create/Manage menu**. That menu, including reuse of the main application actions, belongs to P2-D.

The request itself changes no project state, pan, zoom, selection or active tool.

## Rendering boundary

The P2-C canvas draws only a production-plane/grid foundation used to verify persistent view transform and input behavior. It is not yet the authoritative frame/image renderer.

Actual image/frame layers, transparency, selection overlays, guides, pivot and onion-skin foundations arrive in P2-E. Frame/project synchronization follows in P2-F.

## Intentionally open

Wheel and keyboard semantics remain intentionally open. P2-C does not decide:

- wheel behavior in neutral or tool-active mode;
- keyboard shortcuts;
- Escape-to-deactivate;
- final tool list;
- active-tool persistence between macro environments or sessions;
- final local panel/tab names after the P2-G control audit.

## Acceptance

P2-C is valid when:

1. there is one persistent `SharedCreateCanvas` instance for CREATE;
2. existing route widgets remain reachable and unchanged through `Current Workspace`;
3. Canvas and Current Workspace occupy the same central sector as alternative local pages;
4. neutral LMB click does not pan;
5. neutral LMB drag pans only after the drag threshold;
6. neutral RMB click emits the general context-menu request;
7. active tools own mouse input with no implicit neutral fallback;
8. explicit tool delegation is possible;
9. deactivation/switching/context changes cancel in-flight interactions;
10. pan state survives CREATE route changes because it lives in shared view state;
11. no project persistence schema is changed.
