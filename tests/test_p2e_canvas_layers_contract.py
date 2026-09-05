from __future__ import annotations

from pathlib import Path
import unittest


class P2ECanvasLayersContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.layers = (root / 'app' / 'canvas_layers.py').read_text(encoding='utf-8')
        cls.canvas = (root / 'app' / 'shared_create_canvas.py').read_text(encoding='utf-8')
        cls.main = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        cls.state = (root / 'app' / 'create_workspace_state.py').read_text(encoding='utf-8')
        cls.doc = (root / 'docs' / 'P2E_CANVAS_LAYERS_OVERLAYS.md').read_text(encoding='utf-8')

    def test_shared_canvas_is_real_rgba_renderer_with_separate_cache(self) -> None:
        self.assertIn('CanvasImageLayerCache()', self.canvas)
        self.assertIn('painter.drawImage(target, self._current_qimage)', self.canvas)
        self.assertIn('show_checkerboard', self.canvas)

    def test_main_window_feeds_existing_nondestructive_rgba_result(self) -> None:
        self.assertIn('self.workstation_shell.set_create_canvas_frame_layers(rgba, onion_rgba)', self.main)
        self.assertIn('self.workstation_shell.clear_create_canvas_frame_layers()', self.main)

    def test_overlay_foundations_cover_required_p2e_geometry(self) -> None:
        self.assertIn('class CanvasSelectionRect', self.layers)
        self.assertIn('class CanvasGuideState', self.layers)
        self.assertIn('pivot:', self.layers)
        self.assertIn('ground_y:', self.layers)
        self.assertIn('onion_skin_enabled: bool = False', self.layers)
        self.assertIn('show_pixel_grid', self.layers)

    def test_visual_state_is_metadata_and_renderer_cache_is_not_persistence(self) -> None:
        self.assertNotIn('from app.project_store', self.layers)
        self.assertNotIn('from app.project_session', self.layers)
        self.assertIn('presentation-only', self.doc)
        self.assertIn('not an edit buffer', self.doc)
        self.assertIn('visual: CanvasVisualState', self.state)
        self.assertIn('CanvasImageLayerCache', self.layers)

    def test_p2f_freezes_explicit_single_neighbour_onion_policy(self) -> None:
        self.assertIn("onion_skin_mode: str = 'off'", self.layers)
        self.assertIn('P2-F', self.doc)
        self.assertIn('Off / Previous / Next', self.doc)
        self.assertIn('does not guess an adjacent frame by itself', self.doc)

    def test_coordinate_conversion_is_canvas_owned_for_future_tools(self) -> None:
        self.assertIn('def image_to_canvas(', self.canvas)
        self.assertIn('def canvas_to_image(', self.canvas)
        self.assertIn('image coordinates', self.doc)


if __name__ == '__main__':
    unittest.main()
