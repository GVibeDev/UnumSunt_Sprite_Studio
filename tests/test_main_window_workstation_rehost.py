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

    def test_application_state_writes_only_native_navigation_shape(self) -> None:
        self.assertIn("'state_schema': APP_STATE_SCHEMA_VERSION", self.source)
        self.assertIn("'navigation': navigation.to_dict()", self.source)
        capture = self.source.split('def _capture_app_state', 1)[1].split('def _persist_application_state', 1)[0]
        self.assertNotIn("'current_tab'", capture)
        self.assertNotIn("'current_route'", capture)

    def test_legacy_app_state_migration_is_isolated_outside_main_window(self) -> None:
        self.assertIn('resolve_navigation_state(state, fallback_route_id=fallback)', self.source)
        self.assertNotIn('route_for_legacy_index', self.source)
        self.assertIn('app_state_needs_migration(state)', self.source)

    def test_theme_controller_targets_workstation_not_legacy_tab_bar(self) -> None:
        self.assertIn('workstation_provider=lambda: self.workstation_shell', self.source)
        self.assertNotIn('tab_bar_provider=', self.source)


if __name__ == '__main__':
    unittest.main()
