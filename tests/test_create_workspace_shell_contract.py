from __future__ import annotations

from pathlib import Path
import unittest


class CreateWorkspaceShellSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.source = (root / 'app' / 'create_workspace_shell.py').read_text(encoding='utf-8')
        cls.workstation_source = (root / 'app' / 'workstation_shell.py').read_text(encoding='utf-8')
        cls.main_source = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')

    def test_create_shell_is_three_sector_splitter_with_tabbed_side_panels(self) -> None:
        self.assertIn('QSplitter(Qt.Orientation.Horizontal', self.source)
        self.assertIn("object_name='createLeftPanelTabs'", self.source)
        self.assertIn("object_name='createRightPanelTabs'", self.source)
        self.assertIn("('tools', 'Tools')", self.source)
        self.assertIn("('options', 'Options')", self.source)
        self.assertIn("('configuration', 'Configuration')", self.source)
        self.assertIn("('output', 'Output')", self.source)

    def test_center_surface_receives_layout_priority(self) -> None:
        self.assertIn('self._splitter.setStretchFactor(0, 0)', self.source)
        self.assertIn('self._splitter.setStretchFactor(1, 1)', self.source)
        self.assertIn('self._splitter.setStretchFactor(2, 0)', self.source)
        self.assertIn("setObjectName('createProductionHost')", self.source)

    def test_shell_exposes_project_context_and_active_workspace_status(self) -> None:
        self.assertIn("setObjectName('createProjectContextBar')", self.source)
        self.assertIn("setObjectName('createProjectBreadcrumb')", self.source)
        self.assertIn("setObjectName('createActiveWorkspaceLabel')", self.source)
        self.assertIn("f'CHARACTER {subject}'", self.source)
        self.assertIn("f'ANIMATION {animation}'", self.source)
        self.assertIn("f'DIRECTION {direction}'", self.source)

    def test_contextual_toolbar_is_structural_not_a_duplicate_tool_palette(self) -> None:
        self.assertIn("setObjectName('createContextToolbar')", self.source)
        self.assertNotIn('QToolButton', self.source)
        self.assertNotIn('QAction(', self.source)

    def test_existing_create_route_stack_is_wrapped_not_rebuilt(self) -> None:
        self.assertIn('CreateWorkspaceShell(self._stack, parent=self)', self.workstation_source)
        self.assertIn('self._stack.insertWidget(position, widget)', self.workstation_source)
        self.assertIn('return self._registered_widgets.get(str(route_id).strip())', self.workstation_source)

    def test_project_session_drives_context_display(self) -> None:
        self.assertIn('self.project_session.project_state_changed.connect(', self.main_source)
        self.assertIn('self.workstation_shell.set_create_project_context(self.project_session.project_context)', self.main_source)

    def test_p2c_keeps_pointer_dispatch_out_of_structural_shell(self) -> None:
        self.assertIn('SharedCreateCanvas', self.source)
        self.assertNotIn('mousePressEvent', self.source)
        self.assertNotIn('mouseMoveEvent', self.source)
        self.assertNotIn('mouseReleaseEvent', self.source)


if __name__ == '__main__':
    unittest.main()
