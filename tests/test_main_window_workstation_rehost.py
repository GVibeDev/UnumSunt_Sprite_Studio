from __future__ import annotations

from pathlib import Path
import re
import unittest


class MainWindowWorkstationRehostSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (Path(__file__).resolve().parents[1] / 'app' / 'main_window.py').read_text(encoding='utf-8')

    def test_main_window_uses_workstation_shell_as_central_widget(self) -> None:
        self.assertIn('self.workstation_shell = WorkstationShell()', self.source)
        self.assertIn('self.setCentralWidget(self.workstation_shell)', self.source)
        self.assertNotIn('self.workspace_tabs = QTabWidget()', self.source)
        self.assertNotIn('LegacyWorkspaceTabAdapter', self.source)

    def test_no_legacy_top_level_tab_navigation_remains(self) -> None:
        self.assertNotIn('self.workspace_tabs', self.source)
        self.assertNotIn('self._workflow_tab_routes', self.source)
        self.assertNotIn('self.workspace_tabs.addTab(', self.source)

    def test_all_legacy_workspaces_are_registered_by_stable_route_id(self) -> None:
        route_ids = re.findall(
            r"self\.workstation_shell\.register_route\(\s*route_by_id\('([^']+)'\)",
            self.source,
        )
        self.assertEqual(
            set(route_ids),
            {
                'project', 'generation', 'extraction', 'cleanup', 'alignment',
                'smart_selection', 'export', 'production_presets', 'calibration',
                'prompt_builder', 'spritesheet', 'image_generation', 'workflow',
                'character_set',
            },
        )
        self.assertEqual(len(route_ids), 14)

    def test_shell_route_signal_drives_workspace_context(self) -> None:
        self.assertIn(
            'self.workstation_shell.route_changed.connect(self._on_workspace_changed)',
            self.source,
        )
        self.assertIn('def _on_workspace_changed(self, route: str)', self.source)

    def test_menu_and_workflow_navigation_are_route_native(self) -> None:
        self.assertIn("self.workstation_shell.navigate(str(route))", self.source)
        self.assertIn("self.workstation_shell.navigate('generation')", self.source)
        self.assertIn("self.workstation_shell.navigate('extraction')", self.source)

    def test_guided_view_uses_route_visibility_not_legacy_indices(self) -> None:
        self.assertIn('self.workstation_shell.set_visible_routes(', self.source)
        self.assertIn("fallback_route_id='workflow'", self.source)
        self.assertNotIn('visible_indices', self.source)

    def test_application_state_persists_stable_route_id(self) -> None:
        self.assertIn("'current_route': self._current_workspace_route()", self.source)
        self.assertIn("state.get('current_route')", self.source)
        # `current_tab` remains only as a compatibility hint for R5c8/P1-C profiles.
        self.assertIn('route_for_legacy_index(int(legacy_index)).route_id', self.source)

    def test_theme_controller_no_longer_depends_on_legacy_tab_bar(self) -> None:
        self.assertIn('tab_bar_provider=lambda: None', self.source)


if __name__ == '__main__':
    unittest.main()
