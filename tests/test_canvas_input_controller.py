from __future__ import annotations

import unittest

from app.canvas_input import (
    CanvasInputController,
    CanvasPointerEvent,
    PointerButton,
    PointerPhase,
    ToolPointerDisposition,
)


def pointer(
    phase: PointerPhase,
    x: float,
    y: float,
    button: PointerButton = PointerButton.NONE,
    *buttons: PointerButton,
) -> CanvasPointerEvent:
    return CanvasPointerEvent(
        phase=phase,
        x=x,
        y=y,
        button=button,
        buttons=frozenset(buttons),
    )


class DummyTool:
    def __init__(self, dispositions: list[ToolPointerDisposition] | None = None) -> None:
        self.events: list[CanvasPointerEvent] = []
        self.cancel_count = 0
        self.dispositions = list(dispositions or [])

    def handle_pointer_event(self, event: CanvasPointerEvent) -> ToolPointerDisposition:
        self.events.append(event)
        if self.dispositions:
            return self.dispositions.pop(0)
        return ToolPointerDisposition.HANDLED

    def cancel_pointer_interaction(self) -> None:
        self.cancel_count += 1


class InvalidTool:
    def handle_pointer_event(self, event: CanvasPointerEvent):
        return True

    def cancel_pointer_interaction(self) -> None:
        pass


class CanvasInputControllerTests(unittest.TestCase):
    def test_neutral_left_click_does_not_pan(self) -> None:
        controller = CanvasInputController(drag_threshold=3)
        start = controller.dispatch(pointer(PointerPhase.PRESS, 10, 10, PointerButton.LEFT, PointerButton.LEFT))
        end = controller.dispatch(pointer(PointerPhase.RELEASE, 10, 10, PointerButton.LEFT))
        self.assertTrue(start.interaction_started)
        self.assertEqual((start.pan_dx, start.pan_dy), (0.0, 0.0))
        self.assertEqual((end.pan_dx, end.pan_dy), (0.0, 0.0))
        self.assertFalse(end.request_general_context_menu)
        self.assertFalse(controller.has_interaction)

    def test_neutral_left_drag_pans_only_after_threshold(self) -> None:
        controller = CanvasInputController(drag_threshold=3)
        controller.dispatch(pointer(PointerPhase.PRESS, 10, 10, PointerButton.LEFT, PointerButton.LEFT))
        small = controller.dispatch(pointer(PointerPhase.MOVE, 11, 11, PointerButton.NONE, PointerButton.LEFT))
        large = controller.dispatch(pointer(PointerPhase.MOVE, 15, 13, PointerButton.NONE, PointerButton.LEFT))
        next_move = controller.dispatch(pointer(PointerPhase.MOVE, 18, 18, PointerButton.NONE, PointerButton.LEFT))
        self.assertEqual((small.pan_dx, small.pan_dy), (0.0, 0.0))
        self.assertEqual((large.pan_dx, large.pan_dy), (5, 3))
        self.assertEqual((next_move.pan_dx, next_move.pan_dy), (3, 5))

    def test_neutral_right_click_requests_general_context_menu(self) -> None:
        controller = CanvasInputController()
        controller.dispatch(pointer(PointerPhase.PRESS, 30, 40, PointerButton.RIGHT, PointerButton.RIGHT))
        end = controller.dispatch(pointer(PointerPhase.RELEASE, 30, 40, PointerButton.RIGHT))
        self.assertTrue(end.request_general_context_menu)
        self.assertTrue(end.interaction_ended)

    def test_neutral_right_drag_does_not_open_context_menu(self) -> None:
        controller = CanvasInputController(drag_threshold=2)
        controller.dispatch(pointer(PointerPhase.PRESS, 30, 40, PointerButton.RIGHT, PointerButton.RIGHT))
        controller.dispatch(pointer(PointerPhase.MOVE, 40, 50, PointerButton.NONE, PointerButton.RIGHT))
        end = controller.dispatch(pointer(PointerPhase.RELEASE, 40, 50, PointerButton.RIGHT))
        self.assertFalse(end.request_general_context_menu)

    def test_active_tool_receives_left_and_right_inputs_without_neutral_fallback(self) -> None:
        controller = CanvasInputController()
        tool = DummyTool([
            ToolPointerDisposition.IGNORED,
            ToolPointerDisposition.IGNORED,
        ])
        controller.activate_tool('brush', tool)
        press = controller.dispatch(pointer(PointerPhase.PRESS, 1, 2, PointerButton.RIGHT, PointerButton.RIGHT))
        release = controller.dispatch(pointer(PointerPhase.RELEASE, 1, 2, PointerButton.RIGHT))
        self.assertEqual(controller.mode, CanvasInputController.TOOL_ACTIVE)
        self.assertEqual(press.tool_disposition, ToolPointerDisposition.IGNORED)
        self.assertEqual(release.tool_disposition, ToolPointerDisposition.IGNORED)
        self.assertFalse(release.request_general_context_menu)
        self.assertEqual([event.phase for event in tool.events], [PointerPhase.PRESS, PointerPhase.RELEASE])

    def test_tool_can_explicitly_delegate_new_interaction_to_neutral_canvas(self) -> None:
        controller = CanvasInputController(drag_threshold=1)
        tool = DummyTool([ToolPointerDisposition.DELEGATE_NEUTRAL])
        controller.activate_tool('temporary-tool', tool)
        controller.dispatch(pointer(PointerPhase.PRESS, 5, 5, PointerButton.LEFT, PointerButton.LEFT))
        move = controller.dispatch(pointer(PointerPhase.MOVE, 9, 8, PointerButton.NONE, PointerButton.LEFT))
        controller.dispatch(pointer(PointerPhase.RELEASE, 9, 8, PointerButton.LEFT))
        self.assertEqual((move.pan_dx, move.pan_dy), (4, 3))
        self.assertEqual(len(tool.events), 1)
        self.assertEqual(controller.mode, CanvasInputController.TOOL_ACTIVE)

    def test_deactivating_tool_cancels_inflight_tool_interaction(self) -> None:
        controller = CanvasInputController()
        tool = DummyTool()
        controller.activate_tool('brush', tool)
        controller.dispatch(pointer(PointerPhase.PRESS, 1, 1, PointerButton.LEFT, PointerButton.LEFT))
        self.assertTrue(controller.has_interaction)
        controller.deactivate_tool()
        self.assertEqual(tool.cancel_count, 1)
        self.assertFalse(controller.has_interaction)
        self.assertEqual(controller.mode, CanvasInputController.CANVAS_NEUTRAL)

    def test_switching_active_tool_cancels_previous_interaction(self) -> None:
        controller = CanvasInputController()
        first = DummyTool()
        second = DummyTool()
        controller.activate_tool('first', first)
        controller.dispatch(pointer(PointerPhase.PRESS, 1, 1, PointerButton.LEFT, PointerButton.LEFT))
        controller.activate_tool('second', second)
        self.assertEqual(first.cancel_count, 1)
        self.assertEqual(controller.active_tool_id, 'second')
        self.assertFalse(controller.has_interaction)

    def test_orphan_release_after_cancel_is_not_delivered_to_active_tool(self) -> None:
        controller = CanvasInputController()
        tool = DummyTool()
        controller.activate_tool('brush', tool)
        controller.dispatch(pointer(PointerPhase.PRESS, 1, 1, PointerButton.LEFT, PointerButton.LEFT))
        controller.cancel_interaction()
        before = len(tool.events)
        controller.dispatch(pointer(PointerPhase.RELEASE, 1, 1, PointerButton.LEFT))
        self.assertEqual(len(tool.events), before)

    def test_cancel_event_ends_neutral_session_without_side_effect(self) -> None:
        controller = CanvasInputController()
        controller.dispatch(pointer(PointerPhase.PRESS, 1, 1, PointerButton.LEFT, PointerButton.LEFT))
        result = controller.dispatch(pointer(PointerPhase.CANCEL, 1, 1))
        self.assertTrue(result.interaction_ended)
        self.assertEqual((result.pan_dx, result.pan_dy), (0.0, 0.0))
        self.assertFalse(result.request_general_context_menu)

    def test_tool_contract_requires_explicit_disposition(self) -> None:
        controller = CanvasInputController()
        tool = InvalidTool()
        controller.activate_tool('invalid', tool)
        with self.assertRaises(TypeError):
            controller.dispatch(pointer(PointerPhase.PRESS, 0, 0, PointerButton.LEFT, PointerButton.LEFT))


if __name__ == '__main__':
    unittest.main()
