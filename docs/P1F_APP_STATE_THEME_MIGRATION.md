# P1-F — App State / Theme Migration Closure

Status: candidate for validation after P1-E.

## Objective

Close Phase 1 by making the three-environment workstation model authoritative in both application-state persistence and appearance preferences.

This patch does not change the project file format, ProjectStore, ProjectSession, generation engines, CREATE engines, export behavior or AI runtime behavior.

## Native application-state schema

P1-F writes application navigation as:

```json
{
  "state_schema": 2,
  "navigation": {
    "environment": "create",
    "route": "cleanup"
  }
}
```

`navigation.route` is authoritative. The environment is derived and validated against the workstation route registry.

New application-state writes no longer contain `current_tab` or the P1-D transitional `current_route` field.

## One-way navigation migration

Restore order:

1. P1-F `navigation.route`;
2. P1-D `current_route`;
3. R5c8 / P1-C `current_tab` legacy index;
4. canonical fallback route.

Legacy fields are read only inside `app/app_state.py`. When old state is detected, MainWindow rewrites it once using the native P1-F schema.

## Workstation theme

The former tab-gradient preference becomes a workstation accent.

The selected Red / Green / Blue family now styles:

- GENERATE / CREATE / MANAGE macro navigation;
- environment-local route navigation;
- status bar;
- toolbar theme switch.

New preferences persist as:

```json
{
  "workstation_theme": "red"
}
```

The legacy `tab_theme` key remains read-only migration support.

The old `TAB_THEMES`, `DEFAULT_TAB_THEME` and `tab_theme_colors()` API names remain aliases in `ui_theme.py` only to avoid unnecessary compatibility breakage for dormant/third-party imports. Active P1-F application code uses workstation terminology.

## Project compatibility

P1-F does not alter:

- `app/project_store.py`;
- `app/project_session.py`;
- project schema identifiers;
- Project Group persistence;
- asset/pipeline snapshots.

Application preferences remain separate from project files.

## Validation gates

Automated:

- full regression suite;
- native app-state capture tests;
- P1-D and R5c8/P1-C migration tests;
- corrupted/mismatched navigation repair tests;
- workstation theme model tests;
- shell theme application tests;
- source-level guard that MainWindow no longer writes tab-index navigation;
- MainWindow method-count architecture gate;
- compileall.

Manual Windows:

1. start with an existing R5c8/P1-E user profile;
2. confirm the same logical route is restored;
3. close/reopen and confirm the route remains stable;
4. inspect `profiles.json` and confirm new `navigation` + `workstation_theme` keys are present and old `current_tab` / `current_route` / `tab_theme` are no longer written;
5. cycle Red → Green → Blue and confirm GENERATE / CREATE / MANAGE and local route navigation visibly change accent;
6. confirm switching theme does not recreate workspaces or lose current project/group/tool context;
7. confirm project files themselves are unchanged by this migration.

## Phase 1 closure condition

When P1-F passes automated and manual Windows validation, Phase 1 can be declared complete:

- P1-A/B route registry + shell;
- P1-C workspace rehost;
- P1-D native route routing;
- P1-E ProjectSession boundary;
- P1-F app-state/theme migration closure.

The next development stage is Phase 2 — Shared CREATE Workspace / Persistent Canvas Foundation.
