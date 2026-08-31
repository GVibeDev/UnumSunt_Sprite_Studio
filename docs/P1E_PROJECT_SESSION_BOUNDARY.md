# P1-E — ProjectSession Boundary

Status: implementation patch for validation after validated P1-D.

## Purpose

P1-E introduces a runtime project/session boundary without changing the R5c8 project-file schema.

`ProjectStore` remains the single persistence object. `ProjectSession` owns which store is currently active and which Direction Project Group is the current production context.

The intended dependency becomes:

```text
Workspace / MainWindow
        ↓
ProjectSession
        ↓
ProjectStore
```

instead of requiring unrelated workspaces to query `ProjectWorkspace` for the store and active group.

## Scope

P1-E adds `app/project_session.py` and injects one shared ProjectSession into `ProjectWorkspace`.

MainWindow now supplies the same session to project-aware workspaces through their existing provider callbacks:

- Calibration;
- Sprite Sheet;
- Guided Workflows;
- Character Set / Layer Manager.

MainWindow's project/group lookups also use ProjectSession directly.

`ProjectWorkspace.project_store`, `current_project_path`, and `active_group_id` remain compatibility properties during migration, but they delegate to ProjectSession and are no longer the authoritative owners.

## Signal contract

ProjectSession exposes:

- `project_changed(path)`;
- `project_closed()`;
- `active_group_will_change(old_id, new_id)`;
- `active_group_changed(group_id)`.

ProjectWorkspace refreshes its UI and forwards the validated lifecycle signals so existing MainWindow behavior remains compatible.

A group target is validated before `active_group_will_change` is emitted, because listeners may save/quiesce expensive state in response to that signal.

## Compatibility rules

P1-E deliberately does **not**:

- change the project JSON schema/version;
- rewrite ProjectStore;
- cache a duplicate project document in memory;
- migrate pipeline payloads;
- change cleanup/alignment/export/generation engines;
- introduce the Phase 2 ProjectState document model yet.

The project file remains readable/writable by the validated R5c8 line.

## Transitional behavior

ProjectWorkspace still owns Project Group CRUD UI in P1-E. Direct group mutations performed by that UI call `ProjectSession.synchronize_active_group(...)` or `refresh_active_group()` when a mutation changes or refreshes the active context.

This is intentionally transitional. Later work can move group-domain commands behind ProjectSession/services without combining that change with the first boundary patch.

## Validation gates

P1-E is accepted when:

1. all automated tests pass;
2. an existing R5c8 project opens unchanged;
3. an existing active Direction restores correctly;
4. switching Directions preserves the old snapshot-before-switch behavior;
5. Generate/Create/Manage navigation remains unaffected;
6. project-aware workspaces receive the same shared store/group context;
7. deleting the active Direction clears the active production context cleanly;
8. saving/reopening a project retains pipeline state;
9. the project JSON is not rewritten merely by opening it;
10. no regression is observed in the P1-C/P1-D workstation shell.
