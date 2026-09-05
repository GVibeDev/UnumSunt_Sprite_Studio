from __future__ import annotations

from pathlib import Path
import unittest


class SharedCanvasLayersSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.layers_source = (root / 'app' / 'canvas_layers.py').read_text(encoding='utf-8')
        cls.canvas_source = (root / 'app' / 'shared_create_canvas.py').read_text(encoding='utf-8')
        cls.state_source = (root / 'app' / 'create_workspace_state.py').read_text(encoding='utf-8')

    def test_p2e_has_explicit_raster_roles_and_deterministic_stack(self) -> None:
        self.assertIn("ONION_PREVIOUS = 'onion_previous'", self.layers_source)
        self.assertIn("ONION_NEXT = 'onion_next'", self.layers_source)
        self.assertIn("CURRENT_FRAME = 'current_frame'", self.layers_source)
        self.assertIn('class CanvasLayerStack', self.layers_source)
        self.assertIn('_ROLE_ORDER', self.layers_source)

    def test_visual_state_is_ui_state_not_project_document_cache(self) -> None:
        self.assertIn('class CanvasVisualState', self.layers_source)
        self.assertIn('no decoded pixel payloads', self.layers_source.lower())
        self.assertNotIn('ProjectStore', self.state_source)
        self.assertNotIn('pipeline_state', self.layers_source)
        self.assertIn('visual: CanvasVisualState', self.state_source)

    def test_shared_canvas_owns_render_buffers_outside_project_state(self) -> None:
        self.assertIn('self.layers = CanvasImageLayerCache()', self.canvas_source)
        self.assertIn('self._current_qimage: QImage | None = None', self.canvas_source)
        self.assertIn('self._onion_qimage: QImage | None = None', self.canvas_source)
        self.assertIn("visual.layers.upsert('current-frame', CanvasRasterRole.CURRENT_FRAME)", self.canvas_source)
        self.assertNotIn('from app.project_store', self.canvas_source)

    def test_renderer_and_metadata_share_geometry_and_overlay_contract(self) -> None:
        self.assertIn('visual.set_document_size(width, height)', self.canvas_source)
        self.assertIn('self.state.visual.overlays.set_selection_rect(', self.canvas_source)
        self.assertIn('overlays.set_guides(', self.canvas_source)
        self.assertIn('overlays.set_pivot(guides.pivot)', self.canvas_source)

    def test_p2e_foundation_includes_grid_guides_pivot_selection_and_onion(self) -> None:
        for token in (
            'set_onion_layer',
            'show_pixel_grid',
            'set_guides',
            'set_selection_rect',
            'onion_skin_enabled',
        ):
            self.assertIn(token, self.canvas_source)

    def test_p2e_connectivity_keeps_mesh_rig_and_paint_engine_out(self) -> None:
        self.assertIn('def wheelEvent', self.canvas_source)
        self.assertNotIn('mesh', self.canvas_source.lower())
        self.assertNotIn('RigWorkspace', self.canvas_source)
        self.assertNotIn('brush_stroke', self.canvas_source.lower())


if __name__ == '__main__':
    unittest.main()
