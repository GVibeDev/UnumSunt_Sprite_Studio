from __future__ import annotations

from pathlib import Path
import unittest


class P2CCanvasInputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.controller = (root / 'app' / 'canvas_input.py').read_text(encoding='utf-8')
        cls.canvas = (root / 'app' / 'shared_create_canvas.py').read_text(encoding='utf-8')
        cls.shell = (root / 'app' / 'create_workspace_shell.py').read_text(encoding='utf-8')
        cls.doc = (root / 'docs' / 'P2C_PERSISTENT_SHARED_CANVAS_INPUT_CONTROLLER.md').read_text(encoding='utf-8')

    def test_canvas_input_controller_has_frozen_neutral_and_tool_states(self) -> None:
        self.assertIn("CANVAS_NEUTRAL = 'CANVAS_NEUTRAL'", self.controller)
        self.assertIn("TOOL_ACTIVE = 'TOOL_ACTIVE'", self.controller)
        self.assertIn('ToolPointerDisposition.DELEGATE_NEUTRAL', self.controller)

    def test_neutral_left_pan_and_right_context_request_are_centralized(self) -> None:
        self.assertIn('session.button == PointerButton.LEFT', self.controller)
        self.assertIn('request_general_context_menu=request_menu', self.controller)
        self.assertIn('general_context_menu_requested = Signal(QPoint)', self.canvas)

    def test_shared_canvas_is_persistent_and_legacy_workspace_is_same_sector_page(self) -> None:
        self.assertIn("self.production_tabs.addTab(self.shared_canvas, 'Canvas')", self.shell)
        self.assertIn("self.production_tabs.addTab(workspace_page, 'Current Workspace')", self.shell)
        self.assertIn('self.shared_canvas = SharedCreateCanvas', self.shell)

    def test_p2d_menu_and_unfrozen_inputs_are_not_implemented_prematurely(self) -> None:
        self.assertIn('P2-D', self.doc)
        self.assertIn('does not yet build the File/Edit/Generate/Create/Manage menu', self.doc)
        self.assertIn('Wheel and keyboard semantics remain intentionally open', self.doc)

    def test_interaction_session_cancellation_is_documented(self) -> None:
        self.assertIn('Press → move → release remains one interaction session', self.doc)
        self.assertIn('route/context changes cancel an in-flight interaction', self.doc)


if __name__ == '__main__':
    unittest.main()
