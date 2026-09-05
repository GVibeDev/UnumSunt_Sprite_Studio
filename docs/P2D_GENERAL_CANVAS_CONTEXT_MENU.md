# P2-D — General Canvas Context Menu

Status: **VALIDATED**.

P2-D completes the neutral RMB branch introduced in P2-C. The persistent CREATE canvas now has a general context menu that reuses application actions and delegates navigation to the three-environment workstation shell.

## Required cascade structure

Neutral RMB exposes these top-level cascade groups:

- File
- Edit
- Generate
- Create
- Manage

`File` and `Edit` reuse the existing `QAction` instances owned by the application's main menu. P2-D does not duplicate callbacks or create a second implementation of project/file/edit operations.

The three environment submenus provide:

1. an explicit `Open GENERATE` / `Open CREATE` / `Open MANAGE` action;
2. the registered routes belonging to that environment.

Environment switching delegates to `WorkstationShell.set_environment()` and route navigation delegates to `WorkstationShell.navigate()`.

## Side-effect contract

Building or opening the context menu must not alter:

- project state;
- active Direction;
- frame/selection context;
- canvas pan or zoom;
- active tool;
- current route/environment.

Only an explicitly triggered menu action may cause its declared application/navigation effect.

Opening the menu does not mutate project, selection, pan, zoom or tool state. File and Edit entries reuse the same QAction instances owned by the main application menu.

## Active-tool rule remains unchanged

P2-D does not weaken the P2-C priority rule. The general menu is requested only by the neutral canvas RMB interaction. When an operational tool is active, pointer input remains owned by that tool and there is no implicit general-menu fallback. An active tool cannot open this general menu unless it explicitly delegates that interaction to the neutral canvas contract.

## Compatibility boundary

The shared canvas still remains behind the validated legacy CREATE route surface by default. P2-D wires its menu without forcing Clean-up, Alignment, Import, Select, Character Set or Export onto the new canvas before P2-G.

## Manual validation

On Windows:

1. run the full test suite;
2. switch the CREATE center to the shared canvas using the development/test path if available;
3. with no tool active, neutral RMB must open the cascade menu;
4. opening and dismissing the menu without selecting an action must leave project, pan/zoom and route unchanged;
5. File/Edit entries must behave exactly like the same entries in the application menu;
6. Generate/Create/Manage → Open environment must switch macro environment;
7. route entries inside those submenus must navigate through the normal workstation shell;
8. activate a test/registered canvas tool and verify that RMB no longer opens the general menu unless the tool explicitly delegates that behavior.
