from __future__ import annotations

import importlib.util
import os
import unittest


PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QLabel

    from app.workstation_routes import WORKSPACE_ROUTES, route_by_id
    from app.workstation_shell import WorkstationShell


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class WorkstationShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _shell_with_all_routes(self):
        shell = WorkstationShell()
        widgets = {}
        for route in WORKSPACE_ROUTES:
            widget = QLabel(route.route_id)
            widgets[route.route_id] = widget
            shell.register_route(route, widget)
        return shell, widgets

    def test_default_route_preserves_project_start(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        self.assertEqual(shell.current_environment(), 'manage')
        self.assertEqual(shell.current_route(), 'project')

    def test_route_navigation_switches_macro_environment(self) -> None:
        shell, widgets = self._shell_with_all_routes()
        shell.navigate('cleanup')
        self.assertEqual(shell.current_environment(), 'create')
        self.assertEqual(shell.current_route(), 'cleanup')
        self.assertIs(shell.registered_widget('cleanup'), widgets['cleanup'])

    def test_macro_environment_restores_last_route(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        shell.navigate('prompt_builder')
        shell.navigate('cleanup')
        shell.set_environment('generate')
        self.assertEqual(shell.current_route(), 'prompt_builder')
        shell.set_environment('create')
        self.assertEqual(shell.current_route(), 'cleanup')

    def test_environment_initial_route_uses_registry_order_not_registration_order(self) -> None:
        shell = WorkstationShell()
        shell.register_route(route_by_id('extraction'), QLabel('extraction'))
        shell.register_route(route_by_id('cleanup'), QLabel('cleanup'))
        shell.register_route(route_by_id('spritesheet'), QLabel('spritesheet'))
        shell.set_environment('create')
        self.assertEqual(shell.current_route(), 'spritesheet')

    def test_hiding_current_route_falls_back_without_unregistering_widget(self) -> None:
        shell, widgets = self._shell_with_all_routes()
        shell.navigate('cleanup')
        shell.set_route_visible('cleanup', False)
        self.assertEqual(shell.current_environment(), 'create')
        self.assertNotEqual(shell.current_route(), 'cleanup')
        self.assertIs(shell.registered_widget('cleanup'), widgets['cleanup'])
        shell.navigate('cleanup')
        self.assertEqual(shell.current_route(), 'cleanup')
        self.assertIn('cleanup', shell.visible_routes('create'))

    def test_widget_cannot_be_registered_to_two_routes(self) -> None:
        shell = WorkstationShell()
        widget = QLabel('shared')
        shell.register_route(route_by_id('project'), widget)
        with self.assertRaises(ValueError):
            shell.register_route(route_by_id('workflow'), widget)

    def test_unknown_navigation_is_rejected(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        with self.assertRaises(KeyError):
            shell.navigate('missing')
        with self.assertRaises(KeyError):
            shell.set_environment('missing')

    def test_batch_visibility_falls_back_once_to_requested_route(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        shell.navigate('image_generation')
        observed: list[str] = []
        shell.route_changed.connect(observed.append)
        visible = {'project', 'workflow', 'spritesheet', 'extraction', 'cleanup', 'alignment', 'export'}
        shell.set_visible_routes(visible, fallback_route_id='workflow')
        self.assertEqual(shell.current_route(), 'workflow')
        self.assertEqual(shell.current_environment(), 'manage')
        self.assertEqual(observed, ['workflow'])

    def test_batch_visibility_preserves_current_route_when_still_visible(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        shell.navigate('cleanup')
        observed: list[str] = []
        shell.route_changed.connect(observed.append)
        visible = {'project', 'workflow', 'extraction', 'cleanup', 'alignment', 'export'}
        shell.set_visible_routes(visible, fallback_route_id='workflow')
        self.assertEqual(shell.current_route(), 'cleanup')
        self.assertEqual(observed, [])

    def test_batch_visibility_requires_visible_fallback(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        with self.assertRaises(ValueError):
            shell.set_visible_routes({'project'}, fallback_route_id='workflow')

    def test_workstation_theme_applies_without_rebuilding_routes(self) -> None:
        shell, widgets = self._shell_with_all_routes()
        cleanup = widgets['cleanup']
        shell.apply_theme('blue')
        self.assertEqual(shell.theme_name, 'blue')
        self.assertIs(shell.registered_widget('cleanup'), cleanup)
        self.assertIn('workstationRole="macro"', shell.styleSheet())

    def test_invalid_workstation_theme_falls_back_to_default(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        shell.apply_theme('not-a-theme')
        self.assertEqual(shell.theme_name, 'red')


if __name__ == '__main__':
    unittest.main()
