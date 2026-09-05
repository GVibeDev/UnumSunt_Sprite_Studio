from __future__ import annotations

from pathlib import Path

import numpy as np

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.canvas_layers import CanvasGuideState, CanvasSelectionRect
from app.create_control_rehousing import control_plan_for_route
from app.create_frame_context import CreateFrameContext, normalize_onion_skin_mode
from app.create_frame_strip import CreateFrameStrip
from app.create_workspace_state import CreateWorkspaceState
from app.project_state import ProjectContext
from app.shared_create_canvas import SharedCreateCanvas
from app.workstation_routes import WorkspaceRoute


class CreateWorkspaceShell(QWidget):
    """Persistent structural shell for the CREATE environment.

    P2-B deliberately re-houses the existing CREATE workspaces without rewriting
    their tools.  The shell establishes the permanent hierarchy that later
    milestones will populate: project context, contextual toolbar, tabbed side
    sectors, a dominant production area and a shared frame strip.
    """

    route_requested = Signal(str)
    general_canvas_context_menu_requested = Signal(QPoint)
    source_files_dropped = Signal(object)
    frame_requested = Signal(int)
    frame_selection_requested = Signal(object)
    onion_mode_changed = Signal(str)

    _LEFT_MIN_WIDTH = 190
    _RIGHT_MIN_WIDTH = 210
    _CENTER_MIN_WIDTH = 520

    def __init__(
        self,
        routes: tuple[WorkspaceRoute, ...],
        *,
        state: CreateWorkspaceState | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._routes = tuple(sorted(routes, key=lambda route: (route.order, route.route_id)))
        self._positions = {route.route_id: index for index, route in enumerate(self._routes)}
        self._routes_by_id = {route.route_id: route for route in self._routes}
        self._buttons: dict[str, QPushButton] = {}
        self._registered: dict[str, QWidget] = {}
        self._enabled: dict[str, bool] = {route.route_id: True for route in self._routes}
        self._visible: dict[str, bool] = {route.route_id: True for route in self._routes}
        self._current_route: str | None = None
        self._project_context = ProjectContext()
        self.state = state or CreateWorkspaceState()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_context_bar(root)
        self._build_contextual_toolbar(root)
        self._build_workspace_body(root)
        self._build_frame_strip(root)
        self._restore_view_state()
        self.update_project_context(self._project_context)

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def _build_context_bar(self, root: QVBoxLayout) -> None:
        bar = QFrame(self)
        bar.setObjectName('createProjectContextBar')
        bar.setProperty('workstationRole', 'createContextBar')
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(10)

        self.project_label = QLabel('Project: —', bar)
        self.project_label.setObjectName('createProjectLabel')
        layout.addWidget(self.project_label)
        layout.addStretch(1)

        self.breadcrumb_label = QLabel('CHARACTER —  ›  ANIMATION —  ›  DIRECTION —  ›  SPRITE / FRAME —', bar)
        self.breadcrumb_label.setObjectName('createProjectBreadcrumb')
        layout.addWidget(self.breadcrumb_label, 0)

        self.workspace_label = QLabel('Workspace: —', bar)
        self.workspace_label.setObjectName('createActiveWorkspaceLabel')
        layout.addWidget(self.workspace_label)

        root.addWidget(bar)

    def _build_contextual_toolbar(self, root: QVBoxLayout) -> None:
        toolbar = QFrame(self)
        toolbar.setObjectName('createContextualToolbar')
        toolbar.setProperty('workstationRole', 'createToolbar')
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        for route in self._routes:
            button = QPushButton(route.label, toolbar)
            button.setObjectName(f'workstationRoute_{route.route_id}')
            button.setProperty('workstationRole', 'route')
            button.setCheckable(True)
            button.setEnabled(False)
            button.setToolTip(route.tooltip)
            button.clicked.connect(
                lambda _checked=False, route_id=route.route_id: self._request_route(route_id)
            )
            self._button_group.addButton(button)
            self._buttons[route.route_id] = button
            layout.addWidget(button)

        layout.addStretch(1)

        self.left_panel_toggle = QPushButton('Tools & Options', toolbar)
        self.left_panel_toggle.setObjectName('createLeftPanelToggle')
        self.left_panel_toggle.setProperty('workstationRole', 'panelToggle')
        self.left_panel_toggle.setCheckable(True)
        self.left_panel_toggle.setChecked(not self.state.view.left_panel_collapsed)
        self.left_panel_toggle.toggled.connect(
            lambda checked: self.set_panel_collapsed('left', not checked)
        )
        layout.addWidget(self.left_panel_toggle)

        self.right_panel_toggle = QPushButton('Configurations & Output', toolbar)
        self.right_panel_toggle.setObjectName('createRightPanelToggle')
        self.right_panel_toggle.setProperty('workstationRole', 'panelToggle')
        self.right_panel_toggle.setCheckable(True)
        self.right_panel_toggle.setChecked(not self.state.view.right_panel_collapsed)
        self.right_panel_toggle.toggled.connect(
            lambda checked: self.set_panel_collapsed('right', not checked)
        )
        layout.addWidget(self.right_panel_toggle)

        root.addWidget(toolbar)

    def _build_workspace_body(self, root: QVBoxLayout) -> None:
        self._panel_stacks: dict[str, QStackedWidget] = {}
        self._panel_route_layouts: dict[str, dict[str, QVBoxLayout]] = {}
        self._panel_route_placeholders: dict[str, dict[str, QLabel]] = {}
        self._panel_route_has_content: dict[str, dict[str, bool]] = {}

        self.splitter = QSplitter(self)
        self.splitter.setObjectName('createWorkspaceSplitter')
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(5)
        self.splitter.splitterMoved.connect(self._remember_splitter_sizes)

        self.left_panel = QFrame(self.splitter)
        self.left_panel.setObjectName('createToolsOptionsSector')
        self.left_panel.setProperty('workstationRole', 'createSidePanel')
        self.left_panel.setMinimumWidth(self._LEFT_MIN_WIDTH)
        self.left_panel.setMaximumWidth(380)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(4)
        self.left_tabs = QTabWidget(self.left_panel)
        self.left_tabs.setObjectName('createToolsOptionsTabs')
        self.left_tabs.currentChanged.connect(self._remember_left_section)

        # Source stays a single canonical application surface. The buttons reuse
        # the File-menu QActions; audited route-specific source/status controls
        # are re-parented beneath them rather than reimplemented.
        self._source_page = QWidget(self.left_tabs)
        source_layout = QVBoxLayout(self._source_page)
        source_layout.setContentsMargins(8, 8, 8, 8)
        source_layout.setSpacing(7)
        source_hint = QLabel(
            'Open source files through the same File actions used by the application. '
            'Local source files can also be dropped directly on the canvas.',
            self._source_page,
        )
        source_hint.setWordWrap(True)
        source_layout.addWidget(source_hint)
        self.open_video_source_button = QToolButton(self._source_page)
        self.open_video_source_button.setText('Open Video…')
        self.open_video_source_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.open_video_source_button.setEnabled(False)
        source_layout.addWidget(self.open_video_source_button)
        self.open_spritesheet_source_button = QToolButton(self._source_page)
        self.open_spritesheet_source_button.setText('Open Spritesheet…')
        self.open_spritesheet_source_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.open_spritesheet_source_button.setEnabled(False)
        source_layout.addWidget(self.open_spritesheet_source_button)
        source_layout.addWidget(
            self._build_route_panel_stack(
                'source',
                self._source_page,
                'No additional source controls are required for this CREATE route.',
            ),
            1,
        )

        self._left_tools_label = self._build_panel_section_host(
            'tools',
            'No direct tool controls are assigned to this CREATE route.',
        )
        self._left_options_label = self._build_panel_section_host(
            'options',
            'No additional tool options are assigned to this CREATE route.',
        )
        self.left_tabs.addTab(self._source_page, 'Source')
        self.left_tabs.addTab(self._left_tools_label, 'Tools')
        self.left_tabs.addTab(self._left_options_label, 'Options')
        left_layout.addWidget(self.left_tabs)

        self.production_panel = QFrame(self.splitter)
        self.production_panel.setObjectName('createProductionSector')
        self.production_panel.setProperty('workstationRole', 'createProduction')
        self.production_panel.setMinimumWidth(self._CENTER_MIN_WIDTH)
        self.production_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        production_layout = QVBoxLayout(self.production_panel)
        production_layout.setContentsMargins(0, 0, 0, 0)
        production_layout.setSpacing(0)
        # P2-G keeps the validated specialized production widgets reachable while
        # moving their controls into the persistent side sectors. Canvas and the
        # route production surface remain same-sector pages, never side-by-side.
        self.production_tabs = QTabWidget(self.production_panel)
        self.production_tabs.setObjectName('createProductionTabs')

        self.shared_canvas = SharedCreateCanvas(state=self.state, parent=self.production_tabs)
        self.shared_canvas.general_context_menu_requested.connect(
            self.general_canvas_context_menu_requested.emit
        )
        self.shared_canvas.source_files_dropped.connect(self.source_files_dropped.emit)
        self.production_tabs.addTab(self.shared_canvas, 'Canvas')

        workspace_page = QWidget(self.production_tabs)
        workspace_page.setObjectName('createCurrentWorkspacePage')
        workspace_layout = QVBoxLayout(workspace_page)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self._stack = QStackedWidget(workspace_page)
        self._stack.setObjectName('createProductionStack')
        for route in self._routes:
            placeholder = QWidget(self._stack)
            placeholder.setObjectName(f'createWorkspacePlaceholder_{route.route_id}')
            self._stack.addWidget(placeholder)
        workspace_layout.addWidget(self._stack, 1)
        self.production_tabs.addTab(workspace_page, 'Current Workspace')
        self.production_tabs.currentChanged.connect(self._remember_production_section)
        production_layout.addWidget(self.production_tabs, 1)

        self.right_panel = QFrame(self.splitter)
        self.right_panel.setObjectName('createConfigurationsOutputSector')
        self.right_panel.setProperty('workstationRole', 'createSidePanel')
        self.right_panel.setMinimumWidth(self._RIGHT_MIN_WIDTH)
        self.right_panel.setMaximumWidth(420)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(4)
        self.right_tabs = QTabWidget(self.right_panel)
        self.right_tabs.setObjectName('createConfigurationsOutputTabs')
        self.right_tabs.currentChanged.connect(self._remember_right_section)
        self._right_config_label = self._build_panel_section_host(
            'configurations',
            'No route-specific result configuration is assigned here.',
        )
        self._right_output_label = self._build_panel_section_host(
            'output',
            'No route-specific output controls are assigned here.',
        )
        self.right_tabs.addTab(self._right_config_label, 'Configurations')
        self.right_tabs.addTab(self._right_output_label, 'Output')
        right_layout.addWidget(self.right_tabs)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.production_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        root.addWidget(self.splitter, 1)

    def _build_frame_strip(self, root: QVBoxLayout) -> None:
        self.frame_strip = CreateFrameStrip(self)
        self.frame_strip.frame_requested.connect(self.frame_requested.emit)
        self.frame_strip.selection_requested.connect(self.frame_selection_requested.emit)
        self.frame_strip.onion_mode_changed.connect(self._on_onion_mode_changed)
        # Compatibility alias for P2-B/P2-E tests and any transitional code.
        self.frame_context_label = self.frame_strip.frame_context_label
        self.frame_strip.set_onion_mode(self.state.overlays.onion_skin_mode, emit=False)
        root.addWidget(self.frame_strip)

    def _build_panel_section_host(self, section: str, empty_text: str) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_route_panel_stack(section, host, empty_text), 1)
        return host

    def _build_route_panel_stack(
        self,
        section: str,
        parent: QWidget,
        empty_text: str,
    ) -> QStackedWidget:
        stack = QStackedWidget(parent)
        stack.setObjectName(f'createRoutePanelStack_{section}')
        route_layouts: dict[str, QVBoxLayout] = {}
        placeholders: dict[str, QLabel] = {}
        has_content: dict[str, bool] = {}
        for route in self._routes:
            scroll = QScrollArea(stack)
            scroll.setObjectName(f'createRoutePanel_{section}_{route.route_id}')
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body = QWidget(scroll)
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(6, 6, 6, 6)
            body_layout.setSpacing(7)
            placeholder = QLabel(empty_text, body)
            placeholder.setWordWrap(True)
            placeholder.setProperty('workstationRole', 'createPanelHint')
            body_layout.addWidget(placeholder)
            body_layout.addStretch(1)
            scroll.setWidget(body)
            stack.addWidget(scroll)
            route_layouts[route.route_id] = body_layout
            placeholders[route.route_id] = placeholder
            has_content[route.route_id] = False
        self._panel_stacks[section] = stack
        self._panel_route_layouts[section] = route_layouts
        self._panel_route_placeholders[section] = placeholders
        self._panel_route_has_content[section] = has_content
        return stack

    def _add_rehoused_control(self, route_id: str, section: str, control: QWidget) -> None:
        layout = self._panel_route_layouts[section][route_id]
        if not self._panel_route_has_content[section][route_id]:
            placeholder = self._panel_route_placeholders[section][route_id]
            layout.removeWidget(placeholder)
            placeholder.hide()
            self._panel_route_has_content[section][route_id] = True
        layout.insertWidget(max(0, layout.count() - 1), control)

    @staticmethod
    def _nearest_splitter_child(widget: QWidget, route_widget: QWidget) -> QWidget | None:
        current: QWidget | None = widget
        while current is not None and current is not route_widget:
            parent = current.parentWidget()
            if isinstance(parent, QSplitter):
                return current
            current = parent
        return None

    def _rehouse_registered_route_controls(self, route_id: str, widget: QWidget) -> None:
        plan = control_plan_for_route(route_id)
        if plan.expected_widget_class is not None:
            if widget.__class__.__name__ != plan.expected_widget_class:
                return
        elif route_id == 'extraction' and widget.objectName() != 'extractionWorkspace':
            return

        groups = tuple(widget.findChildren(QGroupBox))
        by_title: dict[str, list[QGroupBox]] = {}
        for group in groups:
            by_title.setdefault(group.title(), []).append(group)

        audited: dict[str, QGroupBox] = {}
        for placement in plan.placements:
            matches = by_title.get(placement.title, [])
            if len(matches) != 1:
                raise RuntimeError(
                    f'P2-G control audit mismatch for {route_id}: '
                    f'{placement.title!r} resolved {len(matches)} times.'
                )
            audited[placement.title] = matches[0]

        legacy_columns: list[QWidget] = []
        if plan.collapse_legacy_control_columns:
            for group in audited.values():
                column = self._nearest_splitter_child(group, widget)
                if column is not None and all(column is not item for item in legacy_columns):
                    legacy_columns.append(column)

        for button in widget.findChildren(QPushButton):
            if button.text() in plan.hidden_button_texts:
                button.hide()

        for placement in plan.placements:
            self._add_rehoused_control(route_id, placement.section, audited[placement.title])

        for column in legacy_columns:
            column.hide()
        for splitter in widget.findChildren(QSplitter):
            if splitter.count() == 0:
                splitter.hide()

    def _set_route_panel_context(self, route_id: str, *, prefer_defaults: bool) -> None:
        index = self._positions[route_id]
        for stack in self._panel_stacks.values():
            stack.setCurrentIndex(index)
        if not prefer_defaults:
            return
        plan = control_plan_for_route(route_id)
        left_index = {'Source': 0, 'Tools': 1, 'Options': 2}[plan.preferred_left_section]
        right_index = {'Configurations': 0, 'Output': 1}[plan.preferred_right_section]
        self.left_tabs.setCurrentIndex(left_index)
        self.right_tabs.setCurrentIndex(right_index)

    @staticmethod
    def _placeholder_page(text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        label = QLabel(text, page)
        label.setWordWrap(True)
        label.setProperty('workstationRole', 'createPanelHint')
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _request_route(self, route_id: str) -> None:
        # Selecting a concrete CREATE route means the user is asking for that
        # route's controls. The shared canvas remains persistent and can be
        # restored without reconstruction.
        self.show_workspace_controls()
        self.route_requested.emit(route_id)

    def bind_source_actions(self, *, open_video_action: QAction, open_spritesheet_action: QAction) -> None:
        # QToolButton.defaultAction reuses the exact QAction and therefore the
        # exact File-menu implementation, enabled state and shortcut metadata.
        self.open_video_source_button.setDefaultAction(open_video_action)
        self.open_spritesheet_source_button.setDefaultAction(open_spritesheet_action)

    def show_canvas(self) -> None:
        self.production_tabs.setCurrentWidget(self.shared_canvas)

    def show_workspace_controls(self) -> None:
        self.production_tabs.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Environment-page navigation API used by WorkstationShell
    # ------------------------------------------------------------------
    def register_widget(self, route_id: str, widget: QWidget) -> None:
        if route_id not in self._positions:
            raise KeyError(f'Route {route_id} does not belong to CREATE.')
        existing = self._registered.get(route_id)
        if existing is not None:
            if existing is widget:
                return
            raise ValueError(f'Route {route_id} already has a registered widget.')

        position = self._positions[route_id]
        placeholder = self._stack.widget(position)
        self._stack.removeWidget(placeholder)
        placeholder.setParent(None)
        placeholder.deleteLater()
        self._stack.insertWidget(position, widget)
        self._registered[route_id] = widget
        self._rehouse_registered_route_controls(route_id, widget)
        self._buttons[route_id].setEnabled(self._enabled[route_id])

    def is_registered(self, route_id: str) -> bool:
        return route_id in self._registered

    def registered_widget(self, route_id: str) -> QWidget | None:
        return self._registered.get(route_id)

    def current_route(self) -> str | None:
        return self._current_route

    def first_available_route(self) -> str | None:
        for route in self._routes:
            route_id = route.route_id
            if self.is_registered(route_id) and self._enabled[route_id] and self._visible[route_id]:
                return route_id
        return None

    def select_route(self, route_id: str, *, reveal: bool = False) -> None:
        if route_id not in self._positions:
            raise KeyError(f'Route {route_id} does not belong to CREATE.')
        if not self.is_registered(route_id):
            raise RuntimeError(f'Route {route_id} has no registered workspace widget.')
        if not self._enabled[route_id]:
            raise RuntimeError(f'Route {route_id} is disabled.')

        button = self._buttons[route_id]
        if reveal and not self._visible[route_id]:
            self._visible[route_id] = True
            button.setVisible(True)
        if not self._visible[route_id]:
            raise RuntimeError(f'Route {route_id} is hidden.')

        route_changed = self._current_route != route_id
        if route_changed:
            self.shared_canvas.cancel_pointer_interaction()
        self._stack.setCurrentIndex(self._positions[route_id])
        button.setChecked(True)
        self._current_route = route_id
        self._set_route_panel_context(route_id, prefer_defaults=route_changed)
        route = self._routes_by_id[route_id]
        self.shared_canvas.set_route_context(route.label)
        self.workspace_label.setText(f'Workspace: {route.label}')
        self.workspace_label.setToolTip(route.tooltip)

    def set_route_visible(self, route_id: str, visible: bool) -> str | None:
        if route_id not in self._buttons:
            raise KeyError(f'Route {route_id} does not belong to CREATE.')
        self._visible[route_id] = bool(visible)
        self._buttons[route_id].setVisible(bool(visible))
        if visible or self._current_route != route_id:
            return self._current_route
        return self._select_fallback()

    def set_visible_routes(self, visible_route_ids: set[str]) -> str | None:
        unknown = visible_route_ids.difference(self._positions)
        if unknown:
            raise KeyError(f'Routes do not belong to CREATE: {sorted(unknown)}')
        for route in self._routes:
            route_id = route.route_id
            visible = route_id in visible_route_ids
            self._visible[route_id] = visible
            self._buttons[route_id].setVisible(visible)
        current = self._current_route
        if (
            current is not None
            and current in visible_route_ids
            and self.is_registered(current)
            and self._enabled[current]
        ):
            return current
        return self._select_fallback()

    def set_route_enabled(self, route_id: str, enabled: bool) -> str | None:
        if route_id not in self._buttons:
            raise KeyError(f'Route {route_id} does not belong to CREATE.')
        self._enabled[route_id] = bool(enabled)
        button = self._buttons[route_id]
        button.setEnabled(bool(enabled) and self.is_registered(route_id))
        if enabled or self._current_route != route_id:
            return self._current_route
        return self._select_fallback()

    def visible_routes(self) -> tuple[str, ...]:
        return tuple(route.route_id for route in self._routes if self._visible[route.route_id])

    def _select_fallback(self) -> str | None:
        fallback = self.first_available_route()
        if fallback is None:
            self._current_route = None
            self._stack.setCurrentIndex(-1)
            checked = self._button_group.checkedButton()
            if checked is not None:
                checked.setChecked(False)
            self.workspace_label.setText('Workspace: —')
            self.shared_canvas.set_route_context(None)
            return None
        self.select_route(fallback)
        return fallback

    # ------------------------------------------------------------------
    # Project/context orientation
    # ------------------------------------------------------------------
    def update_project_context(self, context: ProjectContext) -> None:
        if context != self._project_context:
            self.shared_canvas.cancel_pointer_interaction()
        self._project_context = context
        project_name = Path(context.project_path).name if context.project_path else '—'
        self.project_label.setText(f'Project: {project_name}')
        self.project_label.setToolTip(context.project_path or 'No project open')

        subject = context.subject_name or '—'
        animation = context.animation_name or '—'
        direction = context.direction_name or '—'
        tail_parts: list[str] = []
        if context.asset_id:
            tail_parts.append(str(context.asset_id))
        elif context.source_name:
            tail_parts.append(str(context.source_name))
        if context.frame_index is not None:
            tail_parts.append(f'Frame {context.frame_index}')
        tail = ' · '.join(tail_parts) if tail_parts else '—'
        self.breadcrumb_label.setText(
            f'CHARACTER {subject}  ›  ANIMATION {animation}  ›  '
            f'DIRECTION {direction}  ›  SPRITE / FRAME {tail}'
        )
        if not self.frame_strip.context.has_frames:
            self.frame_context_label.setText(
                f'Frame: {context.frame_index}' if context.frame_index is not None else 'Frame: —'
            )


    # ------------------------------------------------------------------
    # Shared frame/project context (P2-F)
    # ------------------------------------------------------------------
    @property
    def frame_context(self) -> CreateFrameContext:
        return self.frame_strip.context

    @property
    def onion_mode(self) -> str:
        return self.state.overlays.onion_skin_mode

    def update_frame_context(self, context: CreateFrameContext) -> None:
        self.frame_strip.update_context(context)

    def clear_frame_context(self) -> None:
        self.frame_strip.clear_context()
        self.shared_canvas.set_onion_layer(None)

    def set_onion_mode(self, mode: str) -> None:
        normalized = normalize_onion_skin_mode(mode)
        self.frame_strip.set_onion_mode(normalized, emit=True)

    def set_onion_opacity(self, value: float) -> None:
        self.shared_canvas.set_onion_skin_opacity(value)

    def _on_onion_mode_changed(self, mode: str) -> None:
        normalized = normalize_onion_skin_mode(mode)
        self.state.overlays.set_onion_mode(normalized)
        self.shared_canvas.set_onion_skin_enabled(normalized != 'off')
        if normalized == 'off':
            self.shared_canvas.set_onion_layer(None)
        self.onion_mode_changed.emit(normalized)

    # ------------------------------------------------------------------
    # UI-only state
    # ------------------------------------------------------------------
    def set_panel_collapsed(self, side: str, collapsed: bool) -> None:
        normalized = str(side).strip().lower()
        if normalized == 'left':
            self.state.view.left_panel_collapsed = bool(collapsed)
            self.left_panel.setVisible(not collapsed)
            if self.left_panel_toggle.isChecked() == bool(collapsed):
                self.left_panel_toggle.setChecked(not collapsed)
            return
        if normalized == 'right':
            self.state.view.right_panel_collapsed = bool(collapsed)
            self.right_panel.setVisible(not collapsed)
            if self.right_panel_toggle.isChecked() == bool(collapsed):
                self.right_panel_toggle.setChecked(not collapsed)
            return
        raise KeyError(f'Unknown CREATE panel side: {side}')

    def _restore_view_state(self) -> None:
        left = self.state.view.left_panel_width or 240
        right = self.state.view.right_panel_width or 300
        center = max(self._CENTER_MIN_WIDTH, 900)
        self.splitter.setSizes([left, center, right])
        self.left_panel.setVisible(not self.state.view.left_panel_collapsed)
        self.right_panel.setVisible(not self.state.view.right_panel_collapsed)

        if self.state.view.left_panel_section in {'Source', 'Tools', 'Options'}:
            self.left_tabs.setCurrentIndex({'Source': 0, 'Tools': 1, 'Options': 2}[self.state.view.left_panel_section])
        if self.state.view.right_panel_section in {'Configurations', 'Output'}:
            self.right_tabs.setCurrentIndex(0 if self.state.view.right_panel_section == 'Configurations' else 1)
        if self.state.view.production_section == 'Canvas':
            self.production_tabs.setCurrentIndex(0)
        else:
            # P2-G keeps specialized production surfaces as the safe default;
            # rehoused controls remain available in the persistent side sectors.
            self.production_tabs.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Shared canvas render-layer boundary (P2-E)
    # ------------------------------------------------------------------
    def set_canvas_frame_layers(
        self,
        current_rgba: np.ndarray | None,
        onion_rgba: np.ndarray | None = None,
    ) -> None:
        self.shared_canvas.set_frame_layers(current_rgba, onion_rgba)

    def set_canvas_onion_layer(self, onion_rgba: np.ndarray | None) -> None:
        self.shared_canvas.set_onion_layer(onion_rgba)

    def clear_canvas_frame_layers(self) -> None:
        self.shared_canvas.clear_frame_layers()

    def set_canvas_selection_rect(self, selection: CanvasSelectionRect | None) -> None:
        self.shared_canvas.set_selection_rect(selection)

    def set_canvas_guides(self, guides: CanvasGuideState) -> None:
        self.shared_canvas.set_guides(guides)

    def cancel_canvas_interaction(self) -> None:
        self.shared_canvas.cancel_pointer_interaction()

    def _remember_splitter_sizes(self, _position: int, _index: int) -> None:
        sizes = self.splitter.sizes()
        if len(sizes) != 3:
            return
        left, _center, right = sizes
        if self.left_panel.isVisible() and left > 0:
            self.state.view.left_panel_width = int(left)
        if self.right_panel.isVisible() and right > 0:
            self.state.view.right_panel_width = int(right)

    def _remember_left_section(self, index: int) -> None:
        if index >= 0:
            self.state.view.left_panel_section = self.left_tabs.tabText(index)

    def _remember_right_section(self, index: int) -> None:
        if index >= 0:
            self.state.view.right_panel_section = self.right_tabs.tabText(index)

    def _remember_production_section(self, index: int) -> None:
        if index >= 0:
            self.state.view.production_section = self.production_tabs.tabText(index)
