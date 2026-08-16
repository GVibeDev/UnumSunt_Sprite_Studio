from __future__ import annotations

import unittest

import numpy as np

from app.alpha_cleanup import (
    erase_alpha_selection_batch,
    rectangle_selection_mask,
    selection_mask_matches_rgba,
)


class CleanupPropagationTests(unittest.TestCase):
    def test_selection_mask_matches_rgba(self) -> None:
        rgba = np.zeros((8, 6, 4), dtype=np.uint8)
        ok = np.zeros((8, 6), dtype=bool)
        bad = np.zeros((7, 6), dtype=bool)
        self.assertTrue(selection_mask_matches_rgba(rgba, ok))
        self.assertFalse(selection_mask_matches_rgba(rgba, bad))

    def test_erase_alpha_selection_batch_applies_same_selection(self) -> None:
        selection = rectangle_selection_mask(6, 6, 1, 1, 4, 4)
        rgba_a = np.full((6, 6, 4), 255, dtype=np.uint8)
        rgba_b = np.full((6, 6, 4), 200, dtype=np.uint8)
        result = erase_alpha_selection_batch({10: rgba_a, 20: rgba_b}, selection)
        self.assertEqual(set(result.keys()), {10, 20})
        self.assertTrue(np.all(result[10][selection] == 0))
        self.assertTrue(np.all(result[20][selection] == 0))
        self.assertTrue(np.all(result[10][~selection] == 255))

    def test_erase_alpha_selection_batch_rejects_mixed_shapes(self) -> None:
        selection = np.zeros((6, 6), dtype=bool)
        rgba_a = np.zeros((6, 6, 4), dtype=np.uint8)
        rgba_b = np.zeros((5, 6, 4), dtype=np.uint8)
        with self.assertRaises(ValueError):
            erase_alpha_selection_batch({0: rgba_a, 1: rgba_b}, selection)


if __name__ == '__main__':
    unittest.main()
