# Migration R5c1b → R5c1c

## Milestone
**R5c1c — Theme Preferences & Status Readability**

## Changes
- Added three application tab themes: **Red**, **Green**, **Blue**.
- Tab text keeps the existing dark→light progression from tab 0 to tab 13.
- Every tab background now follows the inverse light→dark progression.
- Added **File → Preferences…** with the first persistent preference: tab gradient theme.
- Added a persistent toolbar switch cycling **Red → Green → Blue**.
- Added explicit white foreground to the main status bar and dark status/info panels.
- Preference is persisted inside the existing application state.

## Non-goals
- No generation, cleanup, alignment, workflow or export behavior changes.
- No changes to the R5c1b Python build-runtime bootstrap contract.
