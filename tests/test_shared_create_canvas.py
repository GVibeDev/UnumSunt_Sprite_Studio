from __future__ import annotations

import importlib.util
import os
import unittest


PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QLabel

    from app.canvas_input import CanvasInputController, CanvasPointerEvent, PointerButton, PointerPhase, ToolPointerDisposition
    from app.create_workspace_shell import CreateWorkspaceShell
    from app.create_workspace_state import CreateWorkspaceState
    from app.shared_create_canvas import SharedCreateCanvas
    from app.workstation_routes import routes_for_environment
    from app.workstation_shell import WorkstationShell


class DummyTool:
    def __init__(self) -> None:
        self.cancel_count = 0

    def handle_pointer_event(self, event):
        return ToolPointerDisposition.HANDLED

    def cancel_pointer_interaction(self) -> None:
        self.cancel_count += 1


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class SharedCreateCanvasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _registered_create_shell(self):
        state = CreateWorkspaceState()
        shell = CreateWorkspaceShell(routes_for_environment('create'), state=state)
        for route in routes_for_environment('create'):
            shell.register_widget(route.route_id, QLabel(route.route_id))
        return shell, state

    def test_shared_canvas_is_one_persistent_instance_across_create_routes(self) -> None:
        shell, _state = self._registered_create_shell()
        canvas = shell.shared_canvas
        shell.select_route('cleanup')
        shell.select_route('alignment')
        shell.select_route('export')
        self.assertIs(shell.shared_canvas, canvas)

    def test_current_workspace_remains_default_transition_page(self) -> None:
        shell, state = self._registered_create_shell()
        self.assertEqual(shell.production_tabs.tabText(0), 'Canvas')
        self.assertEqual(shell.production_tabs.tabText(1), 'Current Workspace')
        self.assertEqual(shell.production_tabs.currentIndex(), 1)
        self.assertEqual(state.view.production_section, 'Current Workspace')

    def test_canvas_page_selection_persists_in_create_view_state(self) -> None:
        shell, state = self._registered_create_shell()
        shell.production_tabs.setCurrentIndex(0)
        self.assertEqual(state.view.production_section, 'Canvas')
        shell.select_route('cleanup')
        self.assertEqual(shell.production_tabs.currentIndex(), 0)

    def test_canvas_tool_api_updates_transient_tool_state(self) -> None:
        state = CreateWorkspaceState()
        canvas = SharedCreateCanvas(state=state)
        tool = DummyTool()
        canvas.activate_tool('brush', tool)
        self.assertEqual(canvas.input_mode, CanvasInputController.TOOL_ACTIVE)
        self.assertEqual(state.tool.active_tool_id, 'brush')
        canvas.deactivate_tool()
        self.assertEqual(canvas.input_mode, CanvasInputController.CANVAS_NEUTRAL)
        self.assertIsNone(state.tool.active_tool_id)

    def test_create_route_change_cancels_inflight_canvas_interaction(self) -> None:
        shell, _state = self._registered_create_shell()
        shell.select_route('cleanup')
        shell.shared_canvas.input_controller.dispatch(CanvasPointerEvent(
            phase=PointerPhase.PRESS,
            x=10,
            y=10,
            button=PointerButton.LEFT,
            buttons=frozenset({PointerButton.LEFT}),
        ))
        self.assertTrue(shell.shared_canvas.input_controller.has_interaction)
        shell.select_route('alignment')
        self.assertFalse(shell.shared_canvas.input_controller.has_interaction)

    def test_leaving_create_environment_cancels_canvas_interaction(self) -> None:
        shell = WorkstationShell()
        for route_id in ('generation', 'spritesheet', 'project'):
            from app.workstation_routes import route_by_id
            shell.register_route(route_by_id(route_id), QLabel(route_id))
        shell.navigate('spritesheet')
        create = shell.create_workspace_shell()
        create.shared_canvas.input_controller.dispatch(CanvasPointerEvent(
            phase=PointerPhase.PRESS,
            x=10,
            y=10,
            button=PointerButton.LEFT,
            buttons=frozenset({PointerButton.LEFT}),
        ))
        self.assertTrue(create.shared_canvas.input_controller.has_interaction)
        shell.navigate('generation')
        self.assertFalse(create.shared_canvas.input_controller.has_interaction)


if __name__ == '__main__':
    unittest.main()
