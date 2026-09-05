# P2-G CREATE Control Audit & Rehousing — Candidate Patch

Baseline required: `UnumSunt_Sprite_Studio_P2E_P2F_RECONCILED_SOURCE.zip` validated by the author on 2026-09-05.

Apply by overwriting the matching files in that validated source tree. Do not apply to an older R5c8/P2-E snapshot.

## What changes

- adds the declarative seven-route control audit in `app/create_control_rehousing.py`;
- re-houses the existing Qt control groups into the persistent CREATE Source / Tools / Options / Configurations / Output sectors;
- preserves the same control instances, signals and engines;
- collapses obsolete legacy control columns for Import, Extract, Clean-up and Align;
- splits Alignment controls so current-frame controls are no longer compressed by geometry/export controls;
- splits Extract secondary chroma/background groups into Options;
- keeps specialized Clean-up and Alignment canvases in `Current Workspace`;
- records the user-validated P2-E/P2-F state in the Phase 2 documentation.

## Automated gate used for this candidate

- `python -m compileall -q app` — PASS
- `PYTHONPATH=. python -m pytest -q` — 470 passed, 63 skipped, 36 subtests passed
- `PYTHONPATH=. python -m unittest discover -s tests -q` — 533 tests, OK, 63 skipped

The skipped tests are Qt/PySide6-dependent in the build environment used to prepare the patch. Manual Windows validation remains required.

## Manual validation focus

1. Start the application: no `P2-G control audit mismatch` must appear.
2. Visit all seven CREATE routes and verify the declared side-panel placement.
3. Exercise Clean-up painting/selection/undo/redo in `Current Workspace`.
4. Exercise Alignment anchor/pivot/nudge/view/onion/export in `Current Workspace`.
5. Verify Extract chroma/background controls and R1 Export.
6. Verify Import decomposition and pipeline/reference actions.
7. Verify Character Set layer/assignment editing.
8. Verify Export Studio completes a normal export.
9. Switch routes repeatedly: side controls and route state must remain intact.
10. Recheck P2-F frame selection and onion Off/Previous/Next.
