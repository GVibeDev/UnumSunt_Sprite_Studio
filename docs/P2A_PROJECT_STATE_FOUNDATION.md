# P2-A — ProjectState + View/Tool State Foundation

P2-A starts Phase 2 without changing the visible CREATE layout yet.

## Added runtime boundaries

- `app.project_state.ProjectState` — transient project/production identity only.
- `app.project_state.SourceRef` — lightweight source identity, never decoded pixel data.
- `app.project_state.ProjectContext` — read-only breadcrumb/orientation snapshot.
- `app.create_workspace_state.CreateViewState` — pan/zoom/panel presentation state.
- `app.create_workspace_state.ToolState` — explicit neutral vs active tool selection.
- `app.create_workspace_state.CreateWorkspaceState` — future CREATE-owned UI state aggregate.

`ProjectSession` owns one `ProjectState` and emits `project_state_changed` when the session-scoped runtime identity changes.

## Non-duplication rule

ProjectState does not cache:

- project JSON;
- ProjectStore groups;
- pipeline state;
- decoded frames;
- image/alpha buffers;
- mesh/rig/animation payloads.

`ProjectStore` remains the persisted authority. ProjectState carries only the transient identities needed to coordinate a persistent CREATE canvas.

## Group/source invalidation

A project or Direction change clears source/frame/selection/asset runtime identity. A source change clears frame/selection identity. This prevents the future shared canvas from displaying stale frame state from another production context.

## UI state policy

Pan, zoom and panel presentation are separated from project persistence. Active tool selection is also separated and starts neutral by default; persistence of an operational tool remains an explicit future decision.

## Next slice

P2-B will build the actual CREATE structural shell using the validated Phase 2 contract: project breadcrumb, contextual toolbar, three-column layout, dominant canvas sector, and stacked/tabbed local panel presentation for dense control groups.
