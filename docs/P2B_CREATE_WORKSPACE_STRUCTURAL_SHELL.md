# P2-B — CREATE Workspace Structural Shell

Status: implementation candidate for validation.

P2-B turns the CREATE environment into a persistent structural workspace without rewriting the validated R5c8/P1 engines.

## Scope

The CREATE environment now owns one persistent shell with this hierarchy:

1. application menu (still owned by `MainWindow`);
2. persistent GENERATE / CREATE / MANAGE macro navigation (owned by `WorkstationShell`);
3. CREATE project-context bar;
4. CREATE contextual horizontal toolbar / stage navigation;
5. three-sector production body;
6. frame-strip/timeline foundation.

The three production sectors are:

- left: **Tools & Options**;
- center: **Production / Canvas host**;
- right: **Configurations & Output**.

P2-B does not yet migrate the legacy controls into those side sectors. The existing CREATE workspace widgets are re-housed unchanged in the central production host so that validated functionality remains reachable while later milestones audit and move controls deliberately.

## Same-sector stacked/tabbed rule

The left and right sectors use local tabs. Dense controls must not all remain visible simultaneously simply to make a panel "complete". The active local group is shown in the same sector while the other groups remain on another tab/page.

This directly establishes the architecture required to remove the current Alignment failure mode where, even at full-screen size, selected/current-context fields can be compressed by the complete Alignment control set.

The exact final Alignment, Clean-up, Character Set and Export grouping remains intentionally open until P2-G audits the controls that actually exist.

## Canvas priority

The central production sector has the dominant splitter stretch factor and a protected minimum width. Both side sectors are independently collapsible. Their widths and selected local pages are stored in `CreateWorkspaceState` for the lifetime of the CREATE shell.

No final numeric product dimensions are frozen by this milestone; the values in the implementation are defensive layout defaults, not the final visual specification.

## Project context

The context bar is populated from `ProjectSession.project_context` and exposes orientation only:

`CHARACTER / SUBJECT → ANIMATION → DIRECTION → SPRITE / FRAME`

It does not become a second project-management menu and it does not persist a duplicate project document.

## Route compatibility

The seven current CREATE routes remain stable and functional:

- Import (`spritesheet`)
- Extract (`extraction`)
- Select (`smart_selection`)
- Clean-up (`cleanup`)
- Align (`alignment`)
- Character Set (`character_set`)
- Export (`export`)

The same existing widget instance is retained when navigating away from and back to CREATE.

## Explicitly not implemented in P2-B

- shared production canvas rendering;
- neutral-canvas Pan/RMB dispatcher;
- general canvas context menu;
- migration of existing tool/configuration controls into the side sectors;
- centralized frame strip behavior;
- Paint, Mesh, Rig or Animation tools;
- final side-panel tab names or dimensions.

Those remain P2-C onward according to the canonical Phase 2 contract.
