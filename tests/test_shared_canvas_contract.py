from __future__ import annotations

from pathlib import Path
import unittest


class SharedCanvasSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.input_source = (root / 'app' / 'canvas_input.py').read_text(encoding='utf-8')
        cls.canvas_source = (root / 'app' / 'shared_create_canvas.py').read_text(encoding='utf-8')
        cls.shell_source = (root / 'app' / 'create_workspace_shell.py').read_text(encoding='utf-8')
        cls.compat_source = (root / 'app' / 'shared_canvas.py').read_text(encoding='utf-8')

    def test_controller_freezes_neutral_and_tool_active_states(self) -> None:
        self.assertIn("CANVAS_NEUTRAL = 'CANVAS_NEUTRAL'", self.input_source)
        self.assertIn("TOOL_ACTIVE = 'TOOL_ACTIVE'", self.input_source)
        self.assertIn('class CanvasInputController', self.input_source)

    def test_active_tool_has_no_implicit_neutral_fallback_path(self) -> None:
        self.assertIn("DELEGATE_NEUTRAL = 'delegate_neutral'", self.input_source)
        self.assertIn('if disposition == ToolPointerDisposition.DELEGATE_NEUTRAL:', self.input_source)
        self.assertIn('return self._neutral_press(event)', self.input_source)
        self.assertIn('``IGNORED`` intentionally does not fall back to neutral canvas behavior.', self.input_source)

    def test_interaction_cancel_is_owned_by_controller_and_canvas_lifecycle(self) -> None:
        self.assertIn('session.tool_target.cancel_pointer_interaction()', self.input_source)
        self.assertIn('def cancel_pointer_interaction(self)', self.canvas_source)
        self.assertIn('self.cancel_pointer_interaction()', self.canvas_source)
        self.assertIn('def focusOutEvent', self.canvas_source)
        self.assertIn('def hideEvent', self.canvas_source)

    def test_shared_canvas_is_persistent_but_current_workspace_remains_default(self) -> None:
        self.assertIn("self.production_tabs.addTab(self.shared_canvas, 'Canvas')", self.shell_source)
        self.assertIn("self.production_tabs.addTab(workspace_page, 'Current Workspace')", self.shell_source)
        self.assertIn("if self.state.view.production_section == 'Canvas':", self.shell_source)
        self.assertIn('self.production_tabs.setCurrentIndex(1)', self.shell_source)

    def test_general_context_menu_stays_outside_canvas_widget(self) -> None:
        self.assertNotIn('QMenu', self.canvas_source)
        self.assertNotIn('QAction', self.canvas_source)
        self.assertIn('general_context_menu_requested = Signal(QPoint)', self.canvas_source)

    def test_p2e_connectivity_adds_neutral_wheel_without_mesh_policy(self) -> None:
        self.assertIn('def wheelEvent', self.canvas_source)
        self.assertIn('if self.state.tool.has_active_tool:', self.canvas_source)
        self.assertNotIn('mesh', self.canvas_source.lower())

    def test_legacy_module_name_is_only_a_compatibility_alias(self) -> None:
        self.assertIn('from app.shared_create_canvas import SharedCreateCanvas', self.compat_source)
        self.assertNotIn('class SharedCreateCanvas', self.compat_source)


if __name__ == '__main__':
    unittest.main()
