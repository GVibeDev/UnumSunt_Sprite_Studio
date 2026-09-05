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


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class SharedCreateCanvasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_shell_owns_one_persistent_shared_canvas(self) -> None:
        state = CreateWorkspaceState()
        surface = QLabel('legacy')
        shell = CreateWorkspaceShell(surface, state=state)
        canvas = shell.shared_canvas
        self.assertIs(canvas.state, state)
        self.assertEqual(shell.center_mode, 'legacy')
        shell.set_center_mode('canvas')
        self.assertEqual(shell.center_mode, 'canvas')
        self.assertIs(shell.shared_canvas, canvas)
        shell.set_center_mode('legacy')
        self.assertEqual(shell.center_mode, 'legacy')
        self.assertIs(shell.production_surface, surface)

    def test_canvas_pan_updates_create_view_state(self) -> None:
        state = CreateWorkspaceState()
        shell = CreateWorkspaceShell(QLabel('legacy'), state=state)
        canvas = shell.shared_canvas
        canvas.begin_pan()
        canvas.pan_by(12.5, -4.0)
        canvas.end_pan()
        self.assertEqual((state.view.pan_x, state.view.pan_y), (12.5, -4.0))

    def test_project_context_change_cancels_active_canvas_interaction(self) -> None:
        shell = CreateWorkspaceShell(QLabel('legacy'))
        controller = shell.shared_canvas.input_controller
        # Use a neutral press to create an interaction without depending on QTest.
        from app.canvas_input import CanvasPointerEvent, PointerButton, PointerPhase
        controller.handle_pointer_event(
            CanvasPointerEvent(
                phase=PointerPhase.PRESS,
                x=1,
                y=1,
                button=PointerButton.LEFT,
            )
        )
        self.assertTrue(controller.interaction_active)
        shell.set_project_context(ProjectContext(project_path='/tmp/demo', direction_id='dir-a'))
        self.assertFalse(controller.interaction_active)
        self.assertFalse(shell.shared_canvas.mouse_capture_requested)


if __name__ == '__main__':
    unittest.main()
