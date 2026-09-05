from __future__ import annotations

import importlib.util
import os
import unittest

import numpy as np


PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication

    from app.canvas_layers import CanvasGuideState, CanvasRasterRole, CanvasSelectionRect
    from app.create_workspace_state import CreateWorkspaceState
    from app.shared_canvas import SharedCreateCanvas


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class SharedCanvasLayerRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _canvas(self) -> SharedCreateCanvas:
        canvas = SharedCreateCanvas(state=CreateWorkspaceState())
        canvas.resize(800, 600)
        return canvas

    def test_current_raster_establishes_visual_document_geometry(self) -> None:
        canvas = self._canvas()
        canvas.set_frame_layers(np.zeros((24, 32, 4), dtype=np.uint8))
        self.assertEqual(canvas.state.visual.document_size, (32, 24))
        self.assertEqual(canvas.state.visual.layers.ids(), ('current-frame',))

    def test_onion_metadata_tracks_explicit_previous_next_mode(self) -> None:
        canvas = self._canvas()
        current = np.zeros((16, 16, 4), dtype=np.uint8)
        onion = np.zeros((16, 16, 4), dtype=np.uint8)
        canvas.state.overlays.set_onion_mode('next')
        canvas.set_frame_layers(current, onion)
        layer = canvas.state.visual.layers.get('onion-frame')
        self.assertIsNotNone(layer)
        assert layer is not None
        self.assertEqual(layer.role, CanvasRasterRole.ONION_NEXT)
        self.assertTrue(layer.visible)

    def test_image_coordinate_transform_round_trip_preserves_pan_and_zoom(self) -> None:
        state = CreateWorkspaceState()
        state.view.set_view_transform(pan_x=10, pan_y=-5, zoom=2)
        canvas = SharedCreateCanvas(state=state)
        canvas.resize(800, 600)
        canvas.set_frame_layers(np.zeros((20, 40, 4), dtype=np.uint8))
        point = canvas.image_to_canvas(7.5, 11.0)
        self.assertIsNotNone(point)
        assert point is not None
        resolved = canvas.canvas_to_image(point.x(), point.y())
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertAlmostEqual(resolved[0], 7.5, places=4)
        self.assertAlmostEqual(resolved[1], 11.0, places=4)

    def test_overlay_adapters_update_visual_metadata_only(self) -> None:
        state = CreateWorkspaceState()
        canvas = SharedCreateCanvas(state=state)
        canvas.set_selection_rect(CanvasSelectionRect(1, 2, 8, 9))
        canvas.set_guides(CanvasGuideState.build(
            vertical=(3,),
            horizontal=(6,),
            pivot=(5, 7),
            ground_y=10,
        ))
        overlays = state.visual.overlays
        self.assertEqual(overlays.selection_kind, 'rect')
        self.assertEqual(overlays.selection_rect, (1.0, 2.0, 8.0, 9.0))
        self.assertEqual(overlays.vertical_guides, (3.0,))
        self.assertEqual(overlays.horizontal_guides, (6.0,))
        self.assertEqual(overlays.pivot, (5.0, 7.0))
        self.assertEqual(overlays.ground_y, 10.0)

    def test_clear_frame_layers_keeps_view_transform_and_clears_geometry(self) -> None:
        state = CreateWorkspaceState()
        state.view.set_view_transform(pan_x=31, pan_y=-18, zoom=1.5)
        canvas = SharedCreateCanvas(state=state)
        canvas.set_frame_layers(np.zeros((8, 8, 4), dtype=np.uint8))
        canvas.clear_frame_layers()
        self.assertFalse(canvas.has_image_layer)
        self.assertIsNone(state.visual.document_size)
        self.assertEqual((state.view.pan_x, state.view.pan_y, state.view.zoom), (31.0, -18.0, 1.5))


if __name__ == '__main__':
    unittest.main()
