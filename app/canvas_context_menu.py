from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from app.workstation_routes import (
    ENVIRONMENT_LABELS,
    ENVIRONMENT_ORDER,
    WORKSPACE_ROUTES,
    MacroEnvironment,
    WorkspaceRoute,
)


class GeneralCanvasContextMenu:
    """Build the neutral CREATE canvas context menu from shared application actions.

    File/Edit reuse the exact QAction instances already owned by MainWindow, so the
    canvas menu cannot drift into a second implementation of application commands.
    Generate/Create/Manage navigation is routed through WorkstationShell callbacks.
    Building or opening the menu never mutates project/canvas state by itself.
    """

    def __init__(
        self,
        *,
        parent: QWidget,
        file_actions: Iterable[QAction],
        edit_actions: Iterable[QAction],
        navigate_route: Callable[[str], None],
        set_environment: Callable[[str], None],
        current_route_provider: Callable[[], str | None],
        registered_routes_provider: Callable[[], tuple[str, ...]],
        routes: Iterable[WorkspaceRoute] = WORKSPACE_ROUTES,
    ) -> None:
        self.parent = parent
        self.file_actions = tuple(file_actions)
        self.edit_actions = tuple(edit_actions)
        self.navigate_route = navigate_route
        self.set_environment = set_environment
        self.current_route_provider = current_route_provider
        self.registered_routes_provider = registered_routes_provider
        self.routes = tuple(routes)

    def build_menu(self) -> QMenu:
        menu = QMenu(self.parent)
        menu.setObjectName('generalCanvasContextMenu')

        self._add_shared_action_menu(menu, 'File', self.file_actions, 'canvasContextFileMenu')
        self._add_shared_action_menu(menu, 'Edit', self.edit_actions, 'canvasContextEditMenu')
        menu.addSeparator()

        current_route = self.current_route_provider()
        registered = set(self.registered_routes_provider())
        for environment in ENVIRONMENT_ORDER:
            self._add_environment_menu(
                menu,
                environment,
                current_route=current_route,
                registered=registered,
            )
        return menu

    def show(self, global_position: QPoint) -> None:
        menu = self.build_menu()
        menu.exec(global_position)
        menu.deleteLater()

    @staticmethod
    def _add_shared_action_menu(
        root: QMenu,
        title: str,
        actions: tuple[QAction, ...],
        object_name: str,
    ) -> QMenu:
        submenu = root.addMenu(title)
        submenu.setObjectName(object_name)
        for action in actions:
            submenu.addAction(action)
        return submenu

    def _add_environment_menu(
        self,
        root: QMenu,
        environment: MacroEnvironment,
        *,
        current_route: str | None,
        registered: set[str],
    ) -> QMenu:
        label = ENVIRONMENT_LABELS[environment].title()
        submenu = root.addMenu(label)
        submenu.setObjectName(f'canvasContextEnvironment_{environment}')

        open_environment = submenu.addAction(f'Open {ENVIRONMENT_LABELS[environment]}')
        open_environment.setObjectName(f'canvasContextOpenEnvironment_{environment}')
        open_environment.triggered.connect(
            lambda _checked=False, env=environment: self.set_environment(env)
        )
        submenu.addSeparator()

        for route in self.routes:
            if route.environment != environment:
                continue
            action = submenu.addAction(route.label)
            action.setObjectName(f'canvasContextRoute_{route.route_id}')
            action.setCheckable(True)
            action.setChecked(route.route_id == current_route)
            action.setEnabled(route.route_id in registered)
            action.setToolTip(route.tooltip)
            action.triggered.connect(
                lambda _checked=False, route_id=route.route_id: self.navigate_route(route_id)
            )
        return submenu
