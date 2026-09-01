from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui_theme import DEFAULT_WORKSTATION_THEME, normalize_theme_name, workstation_theme_stylesheet
from app.workstation_routes import (
    DEFAULT_ROUTE_ID,
    ENVIRONMENT_LABELS,
    ENVIRONMENT_ORDER,
    WORKSPACE_ROUTES,
    MacroEnvironment,
    WorkspaceRoute,
    validate_route_registry,
)


class _EnvironmentPage(QWidget):
    route_requested = Signal(str)

    def __init__(self, environment: MacroEnvironment, routes: tuple[WorkspaceRoute, ...]) -> None:
        super().__init__()
        self.environment = environment
        self._routes = tuple(sorted(routes, key=lambda route: (route.order, route.route_id)))
        self._positions = {route.route_id: index for index, route in enumerate(self._routes)}
        self._buttons: dict[str, QPushButton] = {}
        self._registered: dict[str, QWidget] = {}
        self._enabled: dict[str, bool] = {route.route_id: True for route in self._routes}
        self._visible: dict[str, bool] = {route.route_id: True for route in self._routes}
        self._current_route: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        navigation = QWidget(self)
        navigation.setObjectName(f'workstationSubnav_{environment}')
        navigation.setProperty('workstationRole', 'subNavigation')
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(8, 6, 8, 6)
        navigation_layout.setSpacing(6)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._stack = QStackedWidget(self)
        self._stack.setObjectName(f'workstationStack_{environment}')

        for route in self._routes:
            button = QPushButton(route.label, navigation)
            button.setObjectName(f'workstationRoute_{route.route_id}')
            button.setProperty('workstationRole', 'route')
            button.setCheckable(True)
            button.setEnabled(False)
            button.setToolTip(route.tooltip)
            button.clicked.connect(
                lambda _checked=False, route_id=route.route_id: self.route_requested.emit(route_id)
            )
            self._button_group.addButton(button)
            self._buttons[route.route_id] = button
            navigation_layout.addWidget(button)

            placeholder = QWidget(self._stack)
            placeholder.setObjectName(f'workstationPlaceholder_{route.route_id}')
            self._stack.addWidget(placeholder)

        navigation_layout.addStretch(1)
        root.addWidget(navigation)
        root.addWidget(self._stack, 1)

    def register_widget(self, route_id: str, widget: QWidget) -> None:
        if route_id not in self._positions:
            raise KeyError(f'Route {route_id} does not belong to {self.environment}.')
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
            button = self._buttons[route_id]
            if self.is_registered(route_id) and self._enabled[route_id] and self._visible[route_id]:
                return route_id
        return None

    def select_route(self, route_id: str, *, reveal: bool = False) -> None:
        if route_id not in self._positions:
            raise KeyError(f'Route {route_id} does not belong to {self.environment}.')
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

        self._stack.setCurrentIndex(self._positions[route_id])
        button.setChecked(True)
        self._current_route = route_id

    def set_route_visible(self, route_id: str, visible: bool) -> str | None:
        if route_id not in self._buttons:
            raise KeyError(f'Route {route_id} does not belong to {self.environment}.')
        button = self._buttons[route_id]
        self._visible[route_id] = bool(visible)
        button.setVisible(bool(visible))
        if visible or self._current_route != route_id:
            return self._current_route
        return self._select_fallback()

    def set_visible_routes(self, visible_route_ids: set[str]) -> str | None:
        unknown = visible_route_ids.difference(self._positions)
        if unknown:
            raise KeyError(f'Routes do not belong to {self.environment}: {sorted(unknown)}')
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
            raise KeyError(f'Route {route_id} does not belong to {self.environment}.')
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
            return None
        self.select_route(fallback)
        return fallback


class WorkstationShell(QWidget):
    """Three-environment navigation shell for the R5c8+ workstation refactor.

    The shell owns navigation only. Registered workspace widgets remain the same
    instances for the lifetime of the shell and retain their domain/UI state as
    the user moves between GENERATE, CREATE and MANAGE.
    """

    route_changed = Signal(str)
    environment_changed = Signal(str)

    def __init__(
        self,
        *,
        routes: Iterable[WorkspaceRoute] = WORKSPACE_ROUTES,
        default_route_id: str = DEFAULT_ROUTE_ID,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._routes = validate_route_registry(routes)
        self._routes_by_id = {route.route_id: route for route in self._routes}
        if default_route_id not in self._routes_by_id:
            raise KeyError(f'Unknown default workstation route: {default_route_id}')
        self._default_route_id = default_route_id
        self._theme_name = DEFAULT_WORKSTATION_THEME

        self._registered_widgets: dict[str, QWidget] = {}
        self._widget_routes: dict[int, str] = {}
        self._last_route: dict[MacroEnvironment, str | None] = {
            environment: None for environment in ENVIRONMENT_ORDER
        }
        default_environment = self._routes_by_id[default_route_id].environment
        self._current_environment: MacroEnvironment = default_environment

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        macro_navigation = QWidget(self)
        macro_navigation.setObjectName('workstationMacroNavigation')
        macro_navigation.setProperty('workstationRole', 'macroNavigation')
        macro_layout = QHBoxLayout(macro_navigation)
        macro_layout.setContentsMargins(10, 8, 10, 8)
        macro_layout.setSpacing(8)

        self._macro_group = QButtonGroup(self)
        self._macro_group.setExclusive(True)
        self._macro_buttons: dict[MacroEnvironment, QPushButton] = {}
        self._environment_pages: dict[MacroEnvironment, _EnvironmentPage] = {}
        self._environment_positions: dict[MacroEnvironment, int] = {}
        self._environment_stack = QStackedWidget(self)
        self._environment_stack.setObjectName('workstationEnvironmentStack')

        for environment in ENVIRONMENT_ORDER:
            button = QPushButton(ENVIRONMENT_LABELS[environment], macro_navigation)
            button.setObjectName(f'workstationEnvironment_{environment}')
            button.setProperty('workstationRole', 'macro')
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, env=environment: self.set_environment(env)
            )
            self._macro_group.addButton(button)
            self._macro_buttons[environment] = button
            macro_layout.addWidget(button, 1)

            environment_routes = tuple(
                route for route in self._routes if route.environment == environment
            )
            page = _EnvironmentPage(environment, environment_routes)
            page.route_requested.connect(self.navigate)
            self._environment_pages[environment] = page
            self._environment_positions[environment] = self._environment_stack.addWidget(page)

        root.addWidget(macro_navigation)
        root.addWidget(self._environment_stack, 1)
        self._activate_environment(default_environment)
        self.apply_theme(self._theme_name)


    @property
    def theme_name(self) -> str:
        return self._theme_name

    def apply_theme(self, theme_name: str) -> None:
        self._theme_name = normalize_theme_name(theme_name)
        self.setStyleSheet(workstation_theme_stylesheet(self._theme_name))
        self.update()

    def register_route(self, route: WorkspaceRoute, widget: QWidget) -> None:
        canonical = self._routes_by_id.get(route.route_id)
        if canonical is None:
            raise KeyError(f'Unknown workstation route: {route.route_id}')
        if canonical != route:
            raise ValueError(f'Route definition for {route.route_id} does not match the shell registry.')

        existing_route = self._widget_routes.get(id(widget))
        if existing_route is not None and existing_route != route.route_id:
            raise ValueError(
                f'The workspace widget is already registered to route {existing_route}.'
            )
        existing_widget = self._registered_widgets.get(route.route_id)
        if existing_widget is not None:
            if existing_widget is widget:
                return
            raise ValueError(f'Route {route.route_id} already has a registered widget.')

        page = self._environment_pages[route.environment]
        page.register_widget(route.route_id, widget)
        self._registered_widgets[route.route_id] = widget
        self._widget_routes[id(widget)] = route.route_id

        current_initial = self._last_route[route.environment]
        if current_initial is None or route.order < self._routes_by_id[current_initial].order:
            # Registration happens during startup. Keep the canonical lowest-order
            # route as the initial route even when legacy widgets are constructed in
            # their historical tab order (for CREATE this means Import, not Extract).
            page.select_route(route.route_id)
            self._last_route[route.environment] = route.route_id

        if route.route_id == self._default_route_id:
            page.select_route(route.route_id)
            self._last_route[route.environment] = route.route_id
            self._activate_environment(route.environment)

    def navigate(self, route_id: str) -> None:
        normalized = str(route_id).strip()
        route = self._routes_by_id.get(normalized)
        if route is None:
            raise KeyError(f'Unknown workstation route: {route_id}')
        if normalized not in self._registered_widgets:
            raise RuntimeError(f'Route {normalized} has no registered workspace widget.')

        previous_environment = self._current_environment
        previous_route = self.current_route()
        page = self._environment_pages[route.environment]
        page.select_route(normalized, reveal=True)
        self._last_route[route.environment] = normalized
        self._activate_environment(route.environment)

        if previous_environment != route.environment:
            self.environment_changed.emit(route.environment)
        if previous_route != normalized:
            self.route_changed.emit(normalized)

    def set_environment(self, environment: str) -> None:
        normalized = str(environment).strip().lower()
        if normalized not in ENVIRONMENT_ORDER:
            raise KeyError(f'Unknown workstation environment: {environment}')
        env = cast(MacroEnvironment, normalized)
        previous_environment = self._current_environment
        previous_route = self.current_route()
        self._activate_environment(env)

        page = self._environment_pages[env]
        target = self._last_route[env]
        if target is None or not page.is_registered(target):
            target = page.first_available_route()
        if target is not None:
            page.select_route(target)
            self._last_route[env] = target

        if previous_environment != env:
            self.environment_changed.emit(env)
        current_route = self.current_route()
        if current_route is not None and current_route != previous_route:
            self.route_changed.emit(current_route)

    def current_environment(self) -> str:
        return self._current_environment

    def current_route(self) -> str | None:
        return self._last_route[self._current_environment]

    def registered_widget(self, route_id: str) -> QWidget | None:
        return self._registered_widgets.get(str(route_id).strip())

    def registered_routes(self) -> tuple[str, ...]:
        return tuple(
            route.route_id for route in self._routes if route.route_id in self._registered_widgets
        )

    def set_route_visible(self, route_id: str, visible: bool) -> None:
        route = self._require_route(route_id)
        page = self._environment_pages[route.environment]
        previous = page.current_route()
        current = page.set_route_visible(route.route_id, bool(visible))
        self._last_route[route.environment] = current
        if route.environment == self._current_environment and current != previous and current is not None:
            self.route_changed.emit(current)

    def set_visible_routes(
        self,
        route_ids: Iterable[str],
        *,
        fallback_route_id: str | None = None,
    ) -> None:
        visible = {str(route_id).strip() for route_id in route_ids}
        unknown = visible.difference(self._routes_by_id)
        if unknown:
            raise KeyError(f'Unknown workstation routes: {sorted(unknown)}')
        if fallback_route_id is not None:
            fallback_route_id = str(fallback_route_id).strip()
            if fallback_route_id not in self._routes_by_id:
                raise KeyError(f'Unknown fallback workstation route: {fallback_route_id}')
            if fallback_route_id not in visible:
                raise ValueError('The fallback route must remain visible.')

        previous_route = self.current_route()
        for environment in ENVIRONMENT_ORDER:
            page = self._environment_pages[environment]
            environment_visible = {
                route.route_id
                for route in self._routes
                if route.environment == environment and route.route_id in visible
            }
            self._last_route[environment] = page.set_visible_routes(environment_visible)

        current_route = self.current_route()
        if previous_route is not None and previous_route not in visible and fallback_route_id is not None:
            self.navigate(fallback_route_id)
            return
        if current_route is not None and current_route != previous_route:
            self.route_changed.emit(current_route)

    def set_route_enabled(self, route_id: str, enabled: bool) -> None:
        route = self._require_route(route_id)
        page = self._environment_pages[route.environment]
        previous = page.current_route()
        current = page.set_route_enabled(route.route_id, bool(enabled))
        self._last_route[route.environment] = current
        if route.environment == self._current_environment and current != previous and current is not None:
            self.route_changed.emit(current)

    def visible_routes(self, environment: str) -> tuple[str, ...]:
        normalized = str(environment).strip().lower()
        if normalized not in ENVIRONMENT_ORDER:
            raise KeyError(f'Unknown workstation environment: {environment}')
        page = self._environment_pages[cast(MacroEnvironment, normalized)]
        return page.visible_routes()

    def _require_route(self, route_id: str) -> WorkspaceRoute:
        normalized = str(route_id).strip()
        route = self._routes_by_id.get(normalized)
        if route is None:
            raise KeyError(f'Unknown workstation route: {route_id}')
        return route

    def _activate_environment(self, environment: MacroEnvironment) -> None:
        self._current_environment = environment
        self._environment_stack.setCurrentIndex(self._environment_positions[environment])
        self._macro_buttons[environment].setChecked(True)
