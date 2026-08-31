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
        self.assertIn('self.workspace_tabs = LegacyWorkspaceTabAdapter(self.workstation_shell, self)', self.source)
        self.assertIn('self.setCentralWidget(self.workstation_shell)', self.source)
        self.assertNotIn('self.workspace_tabs = QTabWidget()', self.source)

    def test_no_legacy_top_level_add_tab_calls_remain(self) -> None:
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

    def test_phase1c_keeps_legacy_index_adapter_for_next_migration_slice(self) -> None:
        self.assertIn('LegacyWorkspaceTabAdapter', self.source)
        self.assertIn('self._workflow_tab_routes = {', self.source)


if __name__ == '__main__':
    unittest.main()
