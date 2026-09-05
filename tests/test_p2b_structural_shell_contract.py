from __future__ import annotations

from pathlib import Path
import unittest


class P2BStructuralShellContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.create_source = (root / 'app' / 'create_workspace_shell.py').read_text(encoding='utf-8')
        cls.workstation_source = (root / 'app' / 'workstation_shell.py').read_text(encoding='utf-8')
        cls.main_source = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        cls.doc = (root / 'docs' / 'P2B_CREATE_WORKSPACE_STRUCTURAL_SHELL.md').read_text(encoding='utf-8')

    def test_create_uses_one_persistent_specialized_environment_shell(self) -> None:
        self.assertIn("if environment == 'create':", self.workstation_source)
        self.assertIn('page = CreateWorkspaceShell(environment_routes)', self.workstation_source)
        self.assertIn('def create_workspace_shell(self)', self.workstation_source)

    def test_project_context_is_bound_to_project_session_without_new_project_cache(self) -> None:
        self.assertIn('self.workstation_shell.set_create_project_context(self.project_session.project_context)', self.main_source)
        self.assertIn('self.project_session.project_state_changed.connect(', self.main_source)
        self.assertIn('def update_project_context(self, context: ProjectContext)', self.create_source)
        self.assertNotIn('ProjectStore(', self.create_source)

    def test_three_sector_body_uses_tabbed_side_sectors_and_splitter(self) -> None:
        self.assertIn("self.left_tabs.addTab(self._left_tools_label, 'Tools')", self.create_source)
        self.assertIn("self.left_tabs.addTab(self._left_options_label, 'Options')", self.create_source)
        self.assertIn("self.right_tabs.addTab(self._right_config_label, 'Configurations')", self.create_source)
        self.assertIn("self.right_tabs.addTab(self._right_output_label, 'Output')", self.create_source)
        self.assertIn("self.splitter.setStretchFactor(1, 1)", self.create_source)

    def test_canvas_production_sector_is_protected_and_side_sectors_are_collapsible(self) -> None:
        self.assertIn('_CENTER_MIN_WIDTH = 520', self.create_source)
        self.assertIn('self.production_panel.setMinimumWidth(self._CENTER_MIN_WIDTH)', self.create_source)
        self.assertIn("def set_panel_collapsed(self, side: str, collapsed: bool)", self.create_source)
        self.assertIn('left_panel_collapsed', self.create_source)
        self.assertIn('right_panel_collapsed', self.create_source)

    def test_alignment_compression_is_explicitly_deferred_to_control_rehousing_audit(self) -> None:
        self.assertIn('current Alignment failure mode', self.doc)
        self.assertIn('existing CREATE workspace widgets are re-housed unchanged', self.doc)
        self.assertIn('exact final Alignment, Clean-up, Character Set and Export grouping remains intentionally open', self.doc)


if __name__ == '__main__':
    unittest.main()
