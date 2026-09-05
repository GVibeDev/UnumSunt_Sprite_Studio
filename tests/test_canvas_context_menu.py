from __future__ import annotations

import importlib.util
import os
import unittest


PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QApplication, QWidget

    from app.canvas_context_menu import GeneralCanvasContextMenu
    from app.workstation_routes import WORKSPACE_ROUTES


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class GeneralCanvasContextMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _builder(self, *, current_route: str | None = 'cleanup', registered=None):
        parent = QWidget()
        file_action = QAction('Shared File Action', parent)
        edit_action = QAction('Shared Edit Action', parent)
        observed_routes: list[str] = []
        observed_environments: list[str] = []
        registered_routes = tuple(registered if registered is not None else [r.route_id for r in WORKSPACE_ROUTES])
        builder = GeneralCanvasContextMenu(
            parent=parent,
            file_actions=(file_action,),
            edit_actions=(edit_action,),
            navigate_route=observed_routes.append,
            set_environment=observed_environments.append,
            current_route_provider=lambda: current_route,
            registered_routes_provider=lambda: registered_routes,
        )
        return parent, builder, file_action, edit_action, observed_routes, observed_environments

    @staticmethod
    def _submenu(menu, title: str):
        for action in menu.actions():
            if action.text() == title and action.menu() is not None:
                return action.menu()
        raise AssertionError(f'Missing submenu: {title}')

    @staticmethod
    def _action(menu, text: str):
        for action in menu.actions():
            if action.text() == text:
                return action
        raise AssertionError(f'Missing action: {text}')

    def test_top_level_contract_is_file_edit_generate_create_manage(self) -> None:
        _parent, builder, *_rest = self._builder()
        menu = builder.build_menu()
        titles = [action.text() for action in menu.actions() if not action.isSeparator()]
        self.assertEqual(titles, ['File', 'Edit', 'Generate', 'Create', 'Manage'])

    def test_file_and_edit_reuse_exact_main_application_actions(self) -> None:
        _parent, builder, file_action, edit_action, *_rest = self._builder()
        menu = builder.build_menu()
        self.assertIs(self._submenu(menu, 'File').actions()[0], file_action)
        self.assertIs(self._submenu(menu, 'Edit').actions()[0], edit_action)

    def test_building_menu_has_no_navigation_side_effect(self) -> None:
        _parent, builder, _fa, _ea, routes, environments = self._builder()
        builder.build_menu()
        self.assertEqual(routes, [])
        self.assertEqual(environments, [])

    def test_macro_open_action_uses_workstation_environment_callback(self) -> None:
        _parent, builder, _fa, _ea, _routes, environments = self._builder()
        menu = builder.build_menu()
        generate = self._submenu(menu, 'Generate')
        self._action(generate, 'Open GENERATE').trigger()
        self.assertEqual(environments, ['generate'])

    def test_route_action_uses_native_route_callback(self) -> None:
        _parent, builder, _fa, _ea, routes, _environments = self._builder()
        menu = builder.build_menu()
        manage = self._submenu(menu, 'Manage')
        self._action(manage, 'Workflows').trigger()
        self.assertEqual(routes, ['workflow'])

    def test_current_route_is_marked_and_unregistered_route_is_disabled(self) -> None:
        registered = [route.route_id for route in WORKSPACE_ROUTES if route.route_id != 'alignment']
        _parent, builder, *_rest = self._builder(current_route='cleanup', registered=registered)
        menu = builder.build_menu()
        create = self._submenu(menu, 'Create')
        self.assertTrue(self._action(create, 'Clean-up').isChecked())
        self.assertFalse(self._action(create, 'Align').isEnabled())


if __name__ == '__main__':
    unittest.main()
