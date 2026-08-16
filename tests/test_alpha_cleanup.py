from __future__ import annotations

import unittest

import numpy as np

from app.alpha_cleanup import (
    AlphaCleanupSettings,
    apply_alpha_cleanup,
    erase_alpha_selection,
    fill_small_holes,
    map_zoomed_point_to_source,
    polygon_selection_mask,
    rectangle_selection_mask,
    remove_small_islands,
)
from app.alignment_engine import estimate_anchor_by_mode


class AlphaCleanupTests(unittest.TestCase):
    def test_remove_small_islands(self) -> None:
        alpha = np.zeros((20, 20), dtype=np.uint8)
        alpha[5:15, 5:15] = 255
        alpha[1, 1] = 255
        cleaned = remove_small_islands(alpha, min_pixels=2)
        self.assertEqual(int(cleaned[1, 1]), 0)
        self.assertEqual(int(cleaned[10, 10]), 255)

    def test_fill_small_holes(self) -> None:
        alpha = np.zeros((20, 20), dtype=np.uint8)
        alpha[4:16, 4:16] = 255
        alpha[9, 9] = 0
        filled = fill_small_holes(alpha, max_pixels=2)
        self.assertEqual(int(filled[9, 9]), 255)

    def test_apply_cleanup_preserves_rgba_shape(self) -> None:
        rgba = np.zeros((12, 12, 4), dtype=np.uint8)
        rgba[2:10, 2:10, :3] = (100, 50, 25)
        rgba[2:10, 2:10, 3] = 255
        rgba[0, 11, :3] = (100, 50, 25)
        rgba[0, 11, 3] = 255
        cleaned = apply_alpha_cleanup(rgba, AlphaCleanupSettings(remove_islands_min_pixels=2))
        self.assertEqual(cleaned.shape, rgba.shape)
        self.assertEqual(int(cleaned[0, 11, 3]), 0)

    def test_upper_anchor_differs_from_ground_anchor(self) -> None:
        rgba = np.zeros((40, 30, 4), dtype=np.uint8)
        rgba[4:36, 10:20, :3] = (180, 90, 40)
        rgba[4:36, 10:20, 3] = 255
        # Legs / lower mass shifted right
        rgba[24:36, 16:24, :3] = (180, 90, 40)
        rgba[24:36, 16:24, 3] = 255
        ground = estimate_anchor_by_mode(rgba, 'ground')
        upper = estimate_anchor_by_mode(rgba, 'upper_body')
        self.assertGreater(ground[0], upper[0])
        self.assertLess(upper[1], ground[1])

    def test_rectangle_selection_uses_source_coordinates(self) -> None:
        mask = rectangle_selection_mask(10, 12, 2.2, 3.1, 6.0, 7.0)
        self.assertEqual(mask.shape, (10, 12))
        self.assertTrue(mask[3, 2])
        self.assertTrue(mask[6, 5])
        self.assertFalse(mask[2, 2])
        self.assertFalse(mask[7, 6])
        self.assertEqual(int(np.count_nonzero(mask)), 16)

    def test_polygon_selection_rasterizes_inside(self) -> None:
        mask = polygon_selection_mask(12, 12, [(2, 2), (9, 2), (5, 9)])
        self.assertTrue(mask[4, 5])
        self.assertFalse(mask[0, 0])
        self.assertGreater(int(np.count_nonzero(mask)), 20)

    def test_erase_selection_sets_rgba_zero(self) -> None:
        rgba = np.full((8, 8, 4), 255, dtype=np.uint8)
        rgba[:, :, :3] = (120, 80, 40)
        mask = rectangle_selection_mask(8, 8, 2, 2, 5, 5)
        erased = erase_alpha_selection(rgba, mask)
        self.assertTrue(np.all(erased[mask] == 0))
        self.assertTrue(np.all(erased[~mask, 3] == 255))

    def test_erase_selection_rejects_dimension_mismatch(self) -> None:
        rgba = np.zeros((8, 8, 4), dtype=np.uint8)
        with self.assertRaises(ValueError):
            erase_alpha_selection(rgba, np.zeros((7, 8), dtype=bool))

    def test_zoom_mapping_is_independent_of_zoom_level(self) -> None:
        source_a = map_zoomed_point_to_source(40, 64, 8, 100, 80)
        source_b = map_zoomed_point_to_source(20, 32, 4, 100, 80)
        self.assertAlmostEqual(source_a[0], 5.0)
        self.assertAlmostEqual(source_a[1], 8.0)
        self.assertEqual(source_a, source_b)


if __name__ == '__main__':
    unittest.main()
