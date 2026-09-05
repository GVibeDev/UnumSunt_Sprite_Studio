from __future__ import annotations

import importlib.util
import os
import unittest


PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QLabel

    from app.create_workspace_shell import CreateWorkspaceShell
    from app.create_workspace_state import CreateWorkspaceState
    from app.project_state import ProjectContext
    from app.workstation_routes import routes_for_environment


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class CreateWorkspaceShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _shell(self) -> CreateWorkspaceShell:
        return CreateWorkspaceShell(routes_for_environment('create'))

    def _registered_shell(self):
        shell = self._shell()
        widgets = {}
        for route in routes_for_environment('create'):
            widget = QLabel(route.route_id)
            widgets[route.route_id] = widget
            shell.register_widget(route.route_id, widget)
        return shell, widgets

    def test_shell_has_tabbed_left_and_right_sectors(self) -> None:
        shell = self._shell()
        self.assertEqual(shell.left_tabs.count(), 3)
        self.assertEqual(shell.left_tabs.tabText(0), 'Source')
        self.assertEqual(shell.left_tabs.tabText(1), 'Tools')
        self.assertEqual(shell.left_tabs.tabText(2), 'Options')
        self.assertEqual(shell.right_tabs.count(), 2)
        self.assertEqual(shell.right_tabs.tabText(0), 'Configurations')
        self.assertEqual(shell.right_tabs.tabText(1), 'Output')

    def test_route_widget_is_rehoused_without_recreation(self) -> None:
        shell, widgets = self._registered_shell()
        shell.select_route('cleanup')
        self.assertIs(shell.registered_widget('cleanup'), widgets['cleanup'])
        self.assertEqual(shell.current_route(), 'cleanup')
        shell.select_route('alignment')
        shell.select_route('cleanup')
        self.assertIs(shell.registered_widget('cleanup'), widgets['cleanup'])

    def test_route_selection_updates_workspace_orientation(self) -> None:
        shell, _widgets = self._registered_shell()
        shell.select_route('alignment')
        self.assertEqual(shell.workspace_label.text(), 'Workspace: Align')
        shell.select_route('export')
        self.assertEqual(shell.workspace_label.text(), 'Workspace: Export')

    def test_project_context_updates_breadcrumb_without_mutating_navigation(self) -> None:
        shell, _widgets = self._registered_shell()
        shell.select_route('cleanup')
        shell.update_project_context(ProjectContext(
            project_path='C:/projects/Hero',
            subject_name='Hero',
            animation_name='Walk',
            direction_name='East',
            asset_id='body',
            frame_index=4,
        ))
        self.assertEqual(shell.current_route(), 'cleanup')
        self.assertIn('CHARACTER Hero', shell.breadcrumb_label.text())
        self.assertIn('ANIMATION Walk', shell.breadcrumb_label.text())
        self.assertIn('DIRECTION East', shell.breadcrumb_label.text())
        self.assertIn('SPRITE / FRAME body', shell.breadcrumb_label.text())
        self.assertEqual(shell.frame_context_label.text(), 'Frame: 4')

    def test_side_panels_collapse_without_removing_production_widget(self) -> None:
        shell, widgets = self._registered_shell()
        shell.select_route('alignment')
        shell.set_panel_collapsed('left', True)
        shell.set_panel_collapsed('right', True)
        self.assertTrue(shell.left_panel.isHidden())
        self.assertTrue(shell.right_panel.isHidden())
        self.assertIs(shell.registered_widget('alignment'), widgets['alignment'])
        self.assertTrue(shell.state.view.left_panel_collapsed)
        self.assertTrue(shell.state.view.right_panel_collapsed)

    def test_selected_local_panel_pages_live_in_create_view_state(self) -> None:
        state = CreateWorkspaceState()
        shell = CreateWorkspaceShell(routes_for_environment('create'), state=state)
        shell.left_tabs.setCurrentIndex(2)
        shell.right_tabs.setCurrentIndex(1)
        self.assertEqual(state.view.left_panel_section, 'Options')
        self.assertEqual(state.view.right_panel_section, 'Output')

    def test_hidden_current_route_falls_back_and_can_be_explicitly_revealed(self) -> None:
        shell, _widgets = self._registered_shell()
        shell.select_route('cleanup')
        shell.set_route_visible('cleanup', False)
        self.assertNotEqual(shell.current_route(), 'cleanup')
        shell.select_route('cleanup', reveal=True)
        self.assertEqual(shell.current_route(), 'cleanup')
        self.assertIn('cleanup', shell.visible_routes())

    def test_route_button_emits_stable_route_id(self) -> None:
        shell, _widgets = self._registered_shell()
        observed: list[str] = []
        shell.route_requested.connect(observed.append)
        shell._buttons['export'].click()
        self.assertEqual(observed, ['export'])


if __name__ == '__main__':
    unittest.main()
