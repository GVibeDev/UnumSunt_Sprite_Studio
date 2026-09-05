from __future__ import annotations

import unittest

import numpy as np

from app.canvas_layers import (
    CanvasGuideState,
    CanvasImageLayerCache,
    CanvasLayerStack,
    CanvasOverlayState,
    CanvasSelectionRect,
    CanvasRasterRole,
    CanvasVisualState,
)


class CanvasLayerModelTests(unittest.TestCase):
    def test_layer_stack_orders_onions_behind_current_frame(self) -> None:
        stack = CanvasLayerStack()
        stack.upsert('current', CanvasRasterRole.CURRENT_FRAME)
        stack.upsert('next', CanvasRasterRole.ONION_NEXT, opacity=0.25)
        stack.upsert('previous', CanvasRasterRole.ONION_PREVIOUS, opacity=0.25)
        self.assertEqual(stack.ids(), ('previous', 'next', 'current'))

    def test_layer_stack_preserves_same_role_insertion_order(self) -> None:
        stack = CanvasLayerStack()
        stack.upsert('a', CanvasRasterRole.ONION_PREVIOUS)
        stack.upsert('b', CanvasRasterRole.ONION_PREVIOUS)
        self.assertEqual(stack.ids(), ('a', 'b'))

    def test_visible_only_excludes_hidden_and_zero_opacity_layers(self) -> None:
        stack = CanvasLayerStack()
        stack.upsert('a', CanvasRasterRole.ONION_PREVIOUS, visible=False)
        stack.upsert('b', CanvasRasterRole.ONION_NEXT, opacity=0.0)
        stack.upsert('c', CanvasRasterRole.CURRENT_FRAME)
        self.assertEqual(stack.ids(visible_only=True), ('c',))

    def test_layer_opacity_must_be_bounded(self) -> None:
        stack = CanvasLayerStack()
        with self.assertRaises(ValueError):
            stack.upsert('bad', CanvasRasterRole.CURRENT_FRAME, opacity=1.1)
        stack.upsert('ok', CanvasRasterRole.CURRENT_FRAME, opacity=0.5)
        with self.assertRaises(ValueError):
            stack.set_opacity('ok', -0.1)

    def test_overlay_rect_normalizes_reverse_drag(self) -> None:
        overlays = CanvasOverlayState()
        overlays.set_selection_rect(10, 20, 2, 4)
        self.assertEqual(overlays.selection_kind, 'rect')
        self.assertEqual(overlays.selection_rect, (2.0, 4.0, 8.0, 16.0))
        self.assertEqual(overlays.selection_points, ())

    def test_polygon_selection_is_non_destructive_overlay_metadata(self) -> None:
        overlays = CanvasOverlayState()
        overlays.set_selection_polygon(((1, 1), (4, 1), (3, 5)))
        self.assertEqual(overlays.selection_kind, 'polygon')
        self.assertEqual(overlays.selection_points, ((1.0, 1.0), (4.0, 1.0), (3.0, 5.0)))
        overlays.clear_selection()
        self.assertIsNone(overlays.selection_kind)
        self.assertEqual(overlays.selection_points, ())

    def test_guides_and_pivot_are_validated(self) -> None:
        overlays = CanvasOverlayState()
        overlays.set_guides(vertical=(8, 16), horizontal=(24,))
        overlays.set_pivot((12, 30))
        self.assertEqual(overlays.vertical_guides, (8.0, 16.0))
        self.assertEqual(overlays.horizontal_guides, (24.0,))
        self.assertEqual(overlays.pivot, (12.0, 30.0))

    def test_grid_spacing_must_remain_positive(self) -> None:
        overlays = CanvasOverlayState()
        with self.assertRaises(ValueError):
            overlays.set_grid(True, spacing=0)

    def test_visual_state_contains_geometry_metadata_not_pixel_payloads(self) -> None:
        visual = CanvasVisualState()
        self.assertIsNone(visual.document_size)
        visual.set_document_size(96, 64)
        visual.layers.upsert('current', CanvasRasterRole.CURRENT_FRAME)
        self.assertEqual(visual.document_size, (96, 64))
        self.assertFalse(hasattr(visual, 'image'))
        self.assertFalse(hasattr(visual, 'pixels'))


    def test_image_cache_copies_rgba_and_tracks_revision(self) -> None:
        cache = CanvasImageLayerCache()
        source = np.zeros((4, 6, 4), dtype=np.uint8)
        cache.set_images(source)
        source[0, 0, 0] = 255
        self.assertEqual(cache.current_shape, (6, 4))
        self.assertEqual(int(cache.current_view()[0, 0, 0]), 0)
        self.assertEqual(cache.revision, 1)

    def test_image_cache_rejects_mismatched_onion_geometry(self) -> None:
        cache = CanvasImageLayerCache()
        with self.assertRaises(ValueError):
            cache.set_images(
                np.zeros((4, 6, 4), dtype=np.uint8),
                np.zeros((5, 6, 4), dtype=np.uint8),
            )

    def test_image_cache_overlay_adapters_are_transient(self) -> None:
        cache = CanvasImageLayerCache()
        selection = CanvasSelectionRect(1, 2, 3, 4)
        guides = CanvasGuideState.build(vertical=(5,), horizontal=(6,), pivot=(7, 8), ground_y=9)
        cache.set_selection(selection)
        cache.set_guides(guides)
        self.assertEqual(cache.selection, selection)
        self.assertEqual(cache.guides, guides)

    def test_overlay_aliases_share_one_state(self) -> None:
        overlays = CanvasOverlayState()
        overlays.show_checkerboard = False
        overlays.show_pixel_grid = True
        self.assertFalse(overlays.show_transparency)
        self.assertTrue(overlays.show_grid)

    def test_onion_mode_controls_enabled_flag(self) -> None:
        overlays = CanvasOverlayState()
        self.assertFalse(overlays.onion_skin_enabled)
        overlays.set_onion_mode('previous')
        self.assertTrue(overlays.onion_skin_enabled)
        overlays.set_onion_mode('off')
        self.assertFalse(overlays.onion_skin_enabled)

    def test_clear_scene_metadata_resets_layers_overlays_and_geometry(self) -> None:
        visual = CanvasVisualState()
        visual.set_document_size(32, 32)
        visual.layers.upsert('current', CanvasRasterRole.CURRENT_FRAME)
        visual.overlays.set_pivot((4, 8))
        visual.clear_scene_metadata()
        self.assertIsNone(visual.document_size)
        self.assertEqual(len(visual.layers), 0)
        self.assertIsNone(visual.overlays.pivot)


if __name__ == '__main__':
    unittest.main()
