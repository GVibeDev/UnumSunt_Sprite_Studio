# Unum Sunt Sprite Studio — R5c8+ Phase 1 Technical Specification

## Three-environment workstation shell and migration contract

Status: **implementation-ready specification**

Baseline: **R5c8 — validated**

Purpose: replace the current 14 top-level workspace tabs with the first architectural layer of the new workstation:

**GENERATE | CREATE | MANAGE**

Phase 1 changes navigation and ownership boundaries without removing validated production features.

---

# 1. Phase 1 objective

Phase 1 is a structural refactor, not a feature expansion.

The release must preserve the existing R5c8 functional engines while changing the top-level UX from a 14-tab application into a three-environment workstation.

Primary goals:

1. introduce the three macro environments;
2. preserve direct access to every existing R5c8 capability;
3. eliminate navigation by hard-coded tab index;
4. create a route registry independent from widget position;
5. introduce a central project-session boundary without changing the on-disk project format yet;
6. prepare CREATE for a future persistent shared canvas;
7. reduce `MainWindow` as the owner of unrelated domain/UI state;
8. keep R5c8 project compatibility;
9. keep the existing automated regression suite green.

Non-goals for Phase 1:

- no new Paint engine;
- no Mesh;
- no Rig;
- no Animation timeline;
- no project schema migration;
- no Provider JSON system yet;
- no removal of validated engines;
- no rewrite of clean-up/alignment/export logic.

---

# 2. Current architectural facts to preserve

The R5c8 application currently creates all 14 top-level workspaces inside `MainWindow` and places them in one `QTabWidget`.

Current route IDs:

- `project`
- `generation`
- `extraction`
- `cleanup`
- `alignment`
- `smart_selection`
- `export`
- `production_presets`
- `calibration`
- `prompt_builder`
- `spritesheet`
- `image_generation`
- `workflow`
- `character_set`

These route IDs are already useful and should be preserved.

The current implementation also already contains valuable domain separation:

- generation provider registry;
- common provider capabilities;
- generation job manager;
- `ProjectStore`;
- `ProfilesStore`;
- `alpha_cleanup` engine;
- `alignment_engine`;
- `spritesheet_import`;
- `frame_analysis`;
- `export_service`;
- `character_sets`;
- workflow data model;
- calibration data model.

Phase 1 must reuse these components.

---

# 3. New top-level navigation model

Introduce a route registry independent of UI indices.

Recommended file:

`app/workstation_routes.py`

Recommended definitions:

```python
from dataclasses import dataclass
from typing import Literal

MacroEnvironment = Literal["generate", "create", "manage"]


@dataclass(frozen=True)
class WorkspaceRoute:
    route_id: str
    environment: MacroEnvironment
    label: str
    order: int
    tooltip: str
    legacy_index: int
```

Canonical Phase 1 route registry:

```text
GENERATE
  generation          Motion
  image_generation    Image
  prompt_builder      Prompt
  calibration         Calibration

CREATE
  spritesheet         Import
  extraction          Extract
  smart_selection     Select
  cleanup             Clean-up
  alignment           Align
  character_set       Character Set
  export              Export

MANAGE
  project             Projects
  production_presets  Presets
  workflow            Workflows
```

Important:

- `legacy_index` exists only for migration/restoration of old application-state records.
- no new code should navigate by `legacy_index`;
- route ID is the stable navigation contract.

---

# 4. Why the first CREATE navigation is intentionally transitional

The final CREATE concept is:

`Import → Crop → Frames → Paint → Refine → Mesh → Rig → Animate → Export`

Phase 1 must not expose unfinished capabilities as if they already exist.

Therefore the first shell should expose the real R5c8 capabilities:

`Import | Extract | Select | Clean-up | Align | Character Set | Export`

Later phases progressively collapse/reorganize these into the final CREATE model.

Planned transition:

```text
SpriteSheet       → Import / Frames
Extraction        → Frames
Smart Selection   → Frames
Clean-up          → Paint / Refine
Alignment         → Refine / Transform
Character Set     → Layers / production context
Export            → Export
```

New sections such as Crop, Mesh, Rig and Animate appear only when their implementation begins.

---

# 5. WorkstationShell

Introduce:

`app/workstation_shell.py`

Recommended class:

`WorkstationShell(QWidget)`

Responsibilities:

- render the three macro environment controls;
- host registered route widgets;
- render environment-local sub-navigation;
- expose route-based navigation;
- expose route visibility/enabled state;
- emit route changes;
- never own project-domain data.

Suggested interface:

```python
class WorkstationShell(QWidget):
    route_changed = Signal(str)
    environment_changed = Signal(str)

    def register_route(
        self,
        route: WorkspaceRoute,
        widget: QWidget,
    ) -> None: ...

    def navigate(self, route_id: str) -> None: ...

    def current_route(self) -> str: ...

    def current_environment(self) -> str: ...

    def set_route_visible(self, route_id: str, visible: bool) -> None: ...

    def set_route_enabled(self, route_id: str, enabled: bool) -> None: ...

    def visible_routes(self, environment: str) -> tuple[str, ...]: ...
```

Implementation recommendation:

- outer `QVBoxLayout`;
- macro navigation at top;
- one `QStackedWidget` for macro environments;
- each environment owns a small route navigation widget and an internal `QStackedWidget`;
- existing legacy workspace widgets are inserted directly into these stacks.

Do not create copies of legacy workspaces.

---

# 6. Macro navigation UX

Top-level navigation must be visually dominant:

**GENERATE | CREATE | MANAGE**

Requirements:

- always visible;
- changing macro environment must not destroy any child widget;
- current macro must remain obvious;
- keyboard focus should survive normal route changes where possible;
- the selected route inside each environment may be remembered during the session.

Recommended behavior:

```text
Generate → Prompt
Create   → Clean-up
Generate
```

should return to the previously selected Generate route (`Prompt`), not forcibly reset to Motion.

The same principle applies to CREATE and MANAGE.

---

# 7. MainWindow Phase 1 refactor

`MainWindow` currently creates every workspace, owns top-level tab navigation and owns several pieces of current production state.

Phase 1 must change only the navigation boundary first.

## Replace

```python
self.workspace_tabs = QTabWidget()
...
self.workspace_tabs.addTab(...)
```

with:

```python
self.workstation_shell = WorkstationShell()
...
self.workstation_shell.register_route(ROUTES["project"], self.project_workspace)
...
self.setCentralWidget(self.workstation_shell)
```

Workspace construction and signal wiring remain functionally identical in the first patch.

## Remove as authoritative navigation

- `_workflow_tab_routes: dict[str, int]`;
- assumptions that route position equals tab index;
- route lookup through `TAB_ROUTES.index(...)`.

## Replace with

- route registry;
- `workstation_shell.navigate(route_id)`;
- `workstation_shell.current_route()`.

---

# 8. Existing MainWindow state — classification

Current MainWindow state should be classified before migration.

## Project/session domain state

Move progressively toward `ProjectSession` / `ProjectState`:

- current project/store;
- active Project Group;
- current frame index;
- selected frames;
- current source/video;
- generated job association;
- current asset/source references;
- edit overrides;
- pipeline snapshots.

## Tool/UI state

Move progressively toward `ToolState`:

- active macro environment;
- active route;
- zoom;
- active tool;
- temporary selection;
- brush options;
- current color;
- panel visibility.

## Services

Remain services, not project state:

- `ProfilesStore`;
- generation job managers;
- provider registries;
- runtime bridge;
- timers;
- file decoders.

Phase 1 does not need to move every field immediately. The classification is the migration contract.

---

# 9. ProjectSession — first central-state boundary

Introduce:

`app/project_session.py`

Phase 1 should not replace `ProjectStore`.

`ProjectStore` remains the persistence layer.

`ProjectSession` becomes the runtime coordination layer.

Recommended Phase 1 responsibilities:

```python
class ProjectSession(QObject):
    project_opened = Signal(str)
    project_closed = Signal()
    active_group_will_change = Signal(str, str)
    active_group_changed = Signal(str)
    document_reloaded = Signal()
    document_saved = Signal()

    @property
    def store(self) -> ProjectStore | None: ...

    @property
    def project_path(self) -> str | None: ...

    @property
    def active_group_id(self) -> str | None: ...

    def create_project(...) -> None: ...
    def open_project(...) -> None: ...
    def close_project() -> None: ...
    def set_active_group(group_id: str | None) -> None: ...
    def load_document() -> dict: ...
    def save_document(payload: dict) -> None: ...
```

Phase 1 implementation may delegate these calls directly to `ProjectStore`.

Do not duplicate the project JSON in multiple authoritative caches.

---

# 10. ProjectState direction

The later central state should not simply be one enormous serializable dictionary.

Use three layers.

## Persistent ProjectDocument

Serializable project data:

```text
ProjectDocument
- schema_version
- metadata
- assets
- groups
- palettes
- meshes
- rigs
- animations
- pipeline_state
- jobs
- project preset references
- provider profile references
- export profile references
```

## Runtime ProjectState / ProjectSession

Current editing context:

```text
ProjectState
- document/store
- activeGroupId
- currentAssetId
- currentFrame
- selectedFrames
- currentSource
- editOverrides
- undoHistory reference
```

## ToolState

Ephemeral UI state:

```text
ToolState
- currentEnvironment
- currentRoute
- currentTool
- brushSize
- brushOpacity
- foregroundColor
- backgroundColor
- zoom
- selection
- activePanel
- meshMode
- rigMode
```

This prevents brush/UI state from contaminating the project document.

---

# 11. Project schema rule

The existing project file still uses a release-era schema identifier (`R5c3`) even though the application baseline is R5c8.

Do **not** change this in Phase 1.

A later project-schema migration should introduce a schema version independent from the application release, for example:

```json
{
  "schema_version": 2,
  "application_version_last_saved": "R5c9"
}
```

The project-format version must not advance every time the application version changes.

Phase 1 must retain full R5c8 project compatibility.

---

# 12. ProjectWorkspace migration

Current class:

`ProjectWorkspace`

Phase 1 placement:

`MANAGE → Projects`

Phase 1 action:

- keep the widget intact;
- rehost it;
- preserve its current signals;
- connect it to `ProjectSession` progressively.

Future decomposition:

```text
ProjectWorkspace
  ↓
ProjectBrowserPanel
ProjectInspector
ProjectGroupTree
```

`ProjectWorkspace` must ultimately stop being the object other workspaces query to obtain the authoritative `ProjectStore`.

Current patterns such as:

```python
lambda: self.project_workspace.project_store
```

should migrate toward:

```python
lambda: self.project_session.store
```

This is an important decoupling target.

---

# 13. Workspace migration matrix

## GENERATE → Motion

Current:

`GenerationWorkspace`

Keep:

- `GenerationJobManager`;
- `ProviderRegistry`;
- provider contracts;
- generation request/result model;
- WAN frame/FPS contract;
- generation profiles.

Phase 1:

- rehost unchanged.

Later:

- split generic provider/model/prompt/reference/generation panels;
- isolate WanGP-specific runtime fields behind provider-specific configuration.

## GENERATE → Image

Current:

`ImageGenerationWorkspace`

Keep:

- common generation job machinery;
- image provider contract;
- Krea compliance checks;
- normalized image output/manifests.

Phase 1:

- rehost unchanged.

Later:

- merge generic provider/model/reference/generation concepts with Motion into the unified Generate environment;
- keep Krea-specific compliance UI capability/provider-specific.

## GENERATE → Prompt

Current:

`PromptBuilderWorkspace`

Keep:

- `prompt_builder` domain functions;
- Prompt Profile storage;
- explicit apply-to-generation behavior.

Phase 1:

- rehost unchanged.

Later:

- make Prompt a Generate panel instead of an independent application-like page.

## GENERATE → Calibration

Current:

`CalibrationWorkspace`

Keep:

- calibration run model;
- A/B comparison;
- rating;
- generation profile promotion;
- production preset promotion.

Phase 1:

- rehost unchanged.

Later:

- make calibration provider-neutral.

---

## CREATE → Import

Current:

`SpriteSheetWorkspace`

Keep:

- `spritesheet_import`;
- grid detection;
- atlas detection;
- slicing;
- reference-sheet generation;
- sequence manifest generation.

Phase 1:

- rehost unchanged.

Later:

- move source preview into shared CREATE canvas;
- move extracted frames into shared frame strip.

## CREATE → Extract

Current:

MainWindow-built extraction page.

Important technical debt:

- extraction is not a standalone workspace class;
- its widgets are MainWindow members;
- chroma/background controllers are also wired through MainWindow.

Phase 1:

- rehost the existing extraction page as-is.

Phase 2:

- extract it into `ExtractionWorkspace` or decompose into `FramesPanel` + `RefinePanel`;
- remove direct ownership of extraction widgets from MainWindow.

## CREATE → Select

Current:

`SmartSelectionStudio`

Keep:

- `frame_analysis`;
- selection algorithms;
- `SelectedFramesPlayer`;
- analysis/result model.

Phase 1:

- rehost unchanged.

Later:

- integrate into the Frames mode rather than remain a separate pseudo-application.

## CREATE → Clean-up

Current:

`CleanupStudio` + `CleanupCanvas`

Keep aggressively.

The existing implementation already has important pieces required by the future Paint performance contract:

- persistent NumPy/QImage preview backing;
- region-based canvas updates;
- dirty rectangle repaint;
- one history transaction per physical brush stroke;
- direct in-place alpha-buffer editing;
- deferred full transaction commit until stroke end.

Phase 1:

- rehost unchanged.

Phase 3:

- generalize this foundation into the shared Paint engine rather than replacing it.

Missing/future capabilities include:

- generic RGB/RGBA painting;
- color pencil/brush;
- bucket;
- eyedropper;
- palette;
- generic copy/paste;
- stroke interpolation between pointer samples;
- centralized application-wide command stack.

## CREATE → Align

Current:

`AlignmentStudio` + `AlignmentCanvas`

Keep:

- `alignment_engine`;
- output geometry;
- placement/anchor logic;
- alignment export;
- pivot semantics;
- onion-frame concept.

Phase 1:

- rehost unchanged.

Later:

- convert AlignmentCanvas-specific visuals into overlays/interactions of the shared CREATE canvas.

## CREATE → Character Set

Current:

`CharacterSetWorkspace`

Keep:

- `character_sets`;
- non-destructive logical layers;
- subject/animation/direction coverage;
- per-direction layer assignments and offsets.

Phase 1:

- rehost unchanged.

Later:

- split visual layer manipulation toward CREATE;
- allow coverage/library/organizational portions to surface in MANAGE where useful.

## CREATE → Export

Current:

`ExportStudio`

Keep:

- `export_service`;
- raw/aligned frame provider contract;
- bundle/spritesheet export logic.

Phase 1:

- rehost unchanged.

Later:

- keep Export execution in CREATE;
- move reusable Export Profile management to MANAGE.

---

## MANAGE → Presets

Current:

`ProductionPresetsWorkspace`

Keep:

- `ProductionPresetStore`;
- capture/apply semantics;
- non-destructive preset application.

Phase 1:

- rehost unchanged.

Later:

- expand beyond current pipeline sections to palette/crop/resize/tool/animation/provider/export presets.

## MANAGE → Workflows

Current:

`WorkflowWorkspace`

Keep:

- workflow state model;
- optional guided routes;
- step state;
- direct route requests.

Phase 1:

- rehost unchanged.

Behavior change:

- Guided View filters environment-local routes;
- it must not remove the three macro environments or turn them into locked workflow gates.

---

# 14. Existing provider architecture — do not throw it away

The R5c8 generation subsystem is already partly model-agnostic.

It already has:

- `MediaGeneratorProvider`;
- `ImageGeneratorProvider`;
- `VideoGeneratorProvider`;
- `ProviderRegistry`;
- `ProviderCapabilities`;
- normalized `GenerationRequest`;
- normalized `GenerationResult`;
- `GenerationJobManager`.

Therefore Phase 10 is an **extension/generalization**, not a greenfield rewrite.

Future Provider Profiles should sit above/beside this contract.

Recommended eventual layering:

```text
ProviderProfile JSON
        ↓
ProviderDescriptor / Capability Schema
        ↓
ProviderAdapter
        ↓
MediaGeneratorProvider
        ↓
GenerationJobManager
```

WanGP-specific details must move into the WanGP adapter/profile.

---

# 15. Route-based command system

The current toolbar policy is already keyed by logical context strings.

Preserve this direction.

Replace tab-index context with route context.

Recommended:

```python
context = self.workstation_shell.current_route()
```

Existing toolbar policy can continue to operate on route IDs.

Later, policy may be extended with macro environment:

```python
CommandPolicy(
    environments=frozenset({"create"}),
    routes=frozenset({"extraction", "cleanup"}),
    requires_asset=True,
)
```

---

# 16. Workflow routing

Current workflow routes already emit logical route IDs.

Preserve those IDs.

Replace:

```python
index = self._workflow_tab_routes[route]
self.workspace_tabs.setCurrentIndex(index)
```

with:

```python
self.workstation_shell.navigate(route)
```

This removes the strongest coupling between Guided Workflows and the legacy 14-tab structure.

---

# 17. Guided View behavior

Guided View remains optional.

Phase 1 new rule:

- never hide GENERATE / CREATE / MANAGE;
- only filter or de-emphasize environment-local routes;
- an explicit menu/command navigation can temporarily reveal a route;
- project data is never deleted/altered because a route is hidden.

Recommended API:

```python
workstation_shell.set_route_visible(route_id, visible)
```

Route visibility is presentation state, not project state.

---

# 18. Application-state migration

Current user application preferences may contain legacy tab-selection state.

Phase 1 must support one-way compatibility.

Recommended new app-state data:

```json
{
  "navigation": {
    "environment": "create",
    "route": "cleanup"
  },
  "theme": {
    "tab_theme": "red"
  }
}
```

If only a legacy tab index exists:

```text
legacy index → WorkspaceRoute.legacy_index → route_id
```

Then save using the new route-based format.

Do not write new state using raw tab indices.

---

# 19. Theme system

The current theme controller targets a themed tab bar.

Phase 1 options:

Preferred:

- preserve the user theme preference;
- apply it to macro navigation and/or environment-local navigation;
- keep status-bar styling.

Do not delete the theme preference merely because the legacy top-level tab bar disappears.

The visual role changes from “14-tab gradient” to workstation navigation accent.

---

# 20. CREATE shared-canvas preparation — Phase 1 contract only

Phase 1 does not implement the shared canvas.

It must avoid decisions that make it harder later.

Recommended future files:

```text
app/create/
    canvas.py
    canvas_model.py
    overlays/
        base.py
        selection.py
        onion_skin.py
        mesh.py
        rig.py
        guides.py
        cursor.py
    tools/
        base.py
        navigation.py
        paint.py
        selection.py
```

Do not move existing canvas code here during Phase 1 unless required for the shell.

Phase 2 will extract reusable pieces from CleanupCanvas and AlignmentCanvas deliberately.

---

# 21. Shared canvas reuse strategy

Do not try to make `CleanupCanvas` or `AlignmentCanvas` the final shared canvas by adding every future mode directly to one of them.

Instead:

1. preserve both validated widgets during Phase 1;
2. identify reusable interaction/rendering concepts;
3. create a new shared canvas core in Phase 2;
4. port features as overlays/tools;
5. keep engine/domain functions outside the canvas.

Reusable concepts from CleanupCanvas:

- source/screen coordinate mapping;
- pixel grid;
- cursor dirty rectangles;
- persistent image buffer;
- ROI update;
- selection overlays.

Reusable concepts from AlignmentCanvas:

- pivot overlay;
- ground guide;
- onion image;
- drag/nudge interaction;
- nearest-neighbour rendering.

---

# 22. Undo migration strategy

The current Clean-up subsystem already correctly commits one undo transaction per brush stroke.

Do not regress this.

Phase 1:

- leave local history intact.

Phase 2/3:

- introduce a central `QUndoStack` or equivalent command stack;
- migrate commands subsystem by subsystem;
- commands operate on central ProjectState;
- one physical stroke remains one command.

Do not attempt to migrate every existing undo implementation in the same patch as the navigation shell.

---

# 23. Recommended file changes — Phase 1 implementation patch

New:

```text
app/workstation_routes.py
app/workstation_shell.py
app/project_session.py
tests/test_workstation_routes.py
tests/test_project_session.py
docs/PHASE1_WORKSTATION_REFACTOR_SPEC.md
```

Modify:

```text
app/main_window.py
app/ui_commands.py
app/theme_preferences_controller.py
app/preferences_dialog.py        # only if wording/UI must change
app/workflow_workspace.py        # only if Guided View needs shell semantics
tests/...                        # contracts tied to TAB_ROUTES / 14 top-level tabs
```

Do not modify without a concrete need:

```text
app/alpha_cleanup.py
app/alignment_engine.py
app/export_service.py
app/frame_analysis.py
app/spritesheet_import.py
app/character_sets.py
app/generation/manager.py
app/generation/base.py
app/generation/models.py
```

These are validated reusable engines/contracts.

---

# 24. Phase 1 implementation slices

Do not deliver Phase 1 as one giant opaque rewrite.

## P1-A — Route registry

- add `WorkspaceRoute`;
- map all 14 R5c8 routes;
- add pure unit tests;
- no visible UI change.

Gate:

- route IDs unique;
- legacy indices unique;
- every current route mapped;
- environment values valid;
- ordering deterministic.

## P1-B — Workstation shell

- implement macro navigation;
- implement inner route stacks;
- unit/component test navigation;
- allow route registration.

Gate:

- widgets are never duplicated;
- route switching preserves widget instances;
- `navigate(route_id)` selects correct macro + route.

## P1-C — Rehost existing workspaces

- replace top-level `QTabWidget`;
- register current widgets in shell;
- preserve signals;
- preserve menus/toolbar commands.

Gate:

- every R5c8 workspace remains reachable;
- no validated feature is removed.

## P1-D — Route-based workflow/toolbar

- remove hard-coded tab-index routing;
- migrate `_current_workspace_route`;
- migrate workflow route commands;
- migrate Guided View route visibility.

Gate:

- all workflow “Open Step” actions navigate correctly;
- keyboard/menu commands target correct route.

## P1-E — ProjectSession boundary

- add session facade;
- ProjectWorkspace and MainWindow use it where low-risk;
- other workspaces can still use provider lambdas during transition.

Gate:

- create/open project;
- active direction changes;
- save/reload;
- group switching;
- existing project files unchanged.

## P1-F — app-state/theme migration

- save current route by ID;
- restore legacy tab index if found;
- adapt theme to new navigation.

Gate:

- old user profile opens;
- navigation restores;
- no loss of theme preference.

---

# 25. Test plan

Existing full regression suite remains mandatory.

Add at least these tests.

## Route registry

- all 14 legacy routes present;
- no duplicate route IDs;
- no duplicate legacy indices;
- exact environment mapping;
- deterministic order.

## Shell navigation

- default environment/route;
- route navigation switches macro;
- macro change restores last route;
- route visibility does not delete/unregister widget;
- invalid route is rejected cleanly.

## ProjectSession

- empty state;
- create project;
- open existing project;
- active group propagation;
- close/reset;
- no duplicate authoritative store instance.

## Compatibility

- legacy `app_state` tab index restores equivalent route;
- new state persists route ID;
- existing R5c8 project JSON opens without modification merely from opening.

## Workflow

- every workflow step route exists in registry;
- Guided View only refers to registered routes.

## Regression

Run the full R5c8 test suite after every implementation slice.

---

# 26. Phase 1 manual validation

Primary manual scenario:

```text
Open Sprite Studio
↓
GENERATE visible
CREATE visible
MANAGE visible
↓
Open existing R5c8 project
↓
MANAGE → Projects
↓
Activate Direction
↓
GENERATE → Image
↓
GENERATE → Prompt
↓
CREATE → Import
↓
CREATE → Extract
↓
CREATE → Clean-up
↓
CREATE → Align
↓
CREATE → Export
↓
MANAGE → Presets
↓
MANAGE → Workflows
```

Expected:

- project remains loaded;
- active group remains unchanged;
- current source/frame state is not destroyed by macro switching;
- workspaces retain their current instance/state;
- toolbar/menu routing follows logical route;
- no hidden dependency on old tab indices is observable.

---

# 27. Phase 1 success gate

Phase 1 is complete only when:

1. the user sees exactly three primary environments;
2. every current R5c8 capability remains accessible;
3. top-level navigation no longer depends on a 14-item `QTabWidget`;
4. hard-coded route→tab-index navigation is removed from active logic;
5. Guided Workflows navigate by route ID;
6. the project remains compatible with R5c8 files;
7. no engine rewrite was introduced unnecessarily;
8. the full automated suite passes;
9. Windows smoke validation passes;
10. CREATE is ready to receive the persistent canvas in Phase 2.

---

# 28. Immediate recommendation after Phase 1

Do not jump directly to Rig.

Proceed to Phase 2:

**CREATE Workspace Foundation**

Order:

```text
ProjectSession / ProjectState runtime context
↓
Shared Canvas core
↓
Toolbox
↓
Contextual Inspector
↓
Shared Frame Strip
↓
Overlay architecture
↓
Port current Cleanup/Alignment interaction into shared canvas
```

Only after this foundation is stable should the new Paint engine be expanded.

---

# 29. Architectural conclusion

The current codebase does not need to be thrown away.

Several of the hardest foundations already exist:

- provider abstraction;
- generation job normalization;
- project persistence;
- clean-up engine;
- ROI painting updates;
- single-transaction brush strokes;
- alignment engine;
- spritesheet decomposition;
- frame analysis;
- export engine;
- character-set data model.

The immediate problem is primarily **composition and ownership**, not lack of functionality.

Phase 1 therefore changes the application from:

> fourteen top-level feature views wired together by MainWindow

to:

> one workstation shell with stable routes and three coherent environments.

That is the lowest-risk path from R5c8 to the new product architecture.
