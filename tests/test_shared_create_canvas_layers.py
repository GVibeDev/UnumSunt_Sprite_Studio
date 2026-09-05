from __future__ import annotations

import importlib.util
import os
import unittest

import numpy as np


PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication

    from app.canvas_layers import CanvasGuideState, CanvasSelectionRect
    from app.create_workspace_state import CreateWorkspaceState
    from app.shared_create_canvas import SharedCreateCanvas


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class SharedCreateCanvasLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _canvas(self) -> SharedCreateCanvas:
        canvas = SharedCreateCanvas(state=CreateWorkspaceState())
        canvas.resize(800, 600)
        return canvas

    def test_frame_layer_creates_real_image_rect(self) -> None:
        canvas = self._canvas()
        canvas.set_frame_layers(np.zeros((32, 48, 4), dtype=np.uint8))
        rect = canvas.image_rect()
        self.assertIsNotNone(rect)
        assert rect is not None
        self.assertGreater(rect.width(), 0)
        self.assertGreater(rect.height(), 0)
        self.assertTrue(canvas.has_image_layer)

    def test_image_canvas_coordinate_round_trip(self) -> None:
        canvas = self._canvas()
        canvas.set_frame_layers(np.zeros((64, 64, 4), dtype=np.uint8))
        point = canvas.image_to_canvas(12.5, 21.5)
        self.assertIsNotNone(point)
        assert point is not None
        resolved = canvas.canvas_to_image(point.x(), point.y())
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertAlmostEqual(resolved[0], 12.5, places=4)
        self.assertAlmostEqual(resolved[1], 21.5, places=4)

    def test_onion_layer_is_off_by_default_even_when_available(self) -> None:
        canvas = self._canvas()
        current = np.zeros((16, 16, 4), dtype=np.uint8)
        onion = np.zeros((16, 16, 4), dtype=np.uint8)
        canvas.set_frame_layers(current, onion)
        self.assertIsNotNone(canvas.layers.onion_view())
        self.assertFalse(canvas.state.overlays.onion_skin_enabled)

    def test_selection_and_guides_share_image_coordinate_space(self) -> None:
        canvas = self._canvas()
        canvas.set_frame_layers(np.zeros((32, 32, 4), dtype=np.uint8))
        selection = CanvasSelectionRect(2, 3, 5, 6)
        guides = CanvasGuideState.build(vertical=[8], horizontal=[9], pivot=(16, 20), ground_y=24)
        canvas.set_selection_rect(selection)
        canvas.set_guides(guides)
        self.assertEqual(canvas.layers.selection, selection)
        self.assertEqual(canvas.layers.guides, guides)

    def test_clear_frame_layers_keeps_view_transform(self) -> None:
        state = CreateWorkspaceState()
        state.view.set_view_transform(pan_x=31, pan_y=-18, zoom=1.5)
        canvas = SharedCreateCanvas(state=state)
        canvas.set_frame_layers(np.zeros((8, 8, 4), dtype=np.uint8))
        canvas.clear_frame_layers()
        self.assertFalse(canvas.has_image_layer)
        self.assertEqual((state.view.pan_x, state.view.pan_y, state.view.zoom), (31.0, -18.0, 1.5))

    def test_layer_updates_do_not_change_tool_state(self) -> None:
        state = CreateWorkspaceState()
        canvas = SharedCreateCanvas(state=state)
        canvas.set_frame_layers(np.zeros((8, 8, 4), dtype=np.uint8))
        self.assertIsNone(state.tool.active_tool_id)
        canvas.set_onion_skin_enabled(True)
        self.assertIsNone(state.tool.active_tool_id)


if __name__ == '__main__':
    unittest.main()
