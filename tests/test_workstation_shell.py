from __future__ import annotations

import importlib.util
import os
import unittest


PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QLabel

    from app.workstation_routes import WORKSPACE_ROUTES, route_by_id
    from app.workstation_shell import LegacyWorkspaceTabAdapter, WorkstationShell


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
        # Legacy MainWindow constructs Extraction before SpriteSheet. CREATE must
        # still open on Import because it is the canonical lowest-order route.
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


    def test_legacy_adapter_maps_indices_to_shell_routes(self) -> None:
        shell, widgets = self._shell_with_all_routes()
        adapter = LegacyWorkspaceTabAdapter(shell)
        adapter.setCurrentIndex(3)
        self.assertEqual(shell.current_route(), 'cleanup')
        self.assertEqual(adapter.currentIndex(), 3)
        self.assertIs(adapter.widget(3), widgets['cleanup'])
        self.assertEqual(adapter.indexOf(widgets['cleanup']), 3)

    def test_legacy_adapter_visibility_maps_to_route_visibility(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        adapter = LegacyWorkspaceTabAdapter(shell)
        adapter.setCurrentIndex(3)
        adapter.setTabVisible(3, False)
        self.assertFalse(adapter.isTabVisible(3))
        self.assertNotEqual(adapter.currentIndex(), 3)
        adapter.setCurrentIndex(3)
        self.assertTrue(adapter.isTabVisible(3))
        self.assertEqual(adapter.currentIndex(), 3)

    def test_legacy_adapter_emits_legacy_index_on_route_change(self) -> None:
        shell, _widgets = self._shell_with_all_routes()
        adapter = LegacyWorkspaceTabAdapter(shell)
        observed: list[int] = []
        adapter.currentChanged.connect(observed.append)
        shell.navigate('prompt_builder')
        self.assertEqual(observed[-1], 9)


if __name__ == '__main__':
    unittest.main()
