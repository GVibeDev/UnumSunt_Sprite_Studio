from __future__ import annotations

import unittest

import numpy as np

from app.chroma_key import analyze_background, apply_chroma_key
from app.models import ChromaKeySettings


class BackgroundContractTests(unittest.TestCase):
    def test_detects_requested_green_actual_black_mismatch(self) -> None:
        image = np.zeros((80, 100, 3), dtype=np.uint8)
        image[20:70, 30:70] = (180, 110, 70)
        diagnostic = analyze_background(image, requested_rgb=(0, 255, 0))
        self.assertEqual(diagnostic.detected_rgb, (0, 0, 0))
        self.assertTrue(diagnostic.mismatch)
        self.assertEqual(diagnostic.recommended_mode, 'edge_connected')
        self.assertEqual(diagnostic.confidence, 'alta')

    def test_edge_connected_key_preserves_enclosed_dark_detail(self) -> None:
        image = np.zeros((100, 120, 3), dtype=np.uint8)
        image[20:85, 25:95] = (170, 95, 55)
        image[40:60, 50:70] = (0, 0, 0)

        global_settings = ChromaKeySettings(
            background_rgb=(0, 0, 0),
            tolerance=12,
            softness=8,
            cleanup_radius=0,
            edge_decontamination=0,
            keying_mode='global',
        )
        edge_settings = ChromaKeySettings(
            background_rgb=(0, 0, 0),
            tolerance=12,
            softness=8,
            cleanup_radius=0,
            edge_decontamination=0,
            keying_mode='edge_connected',
        )
        _, global_alpha = apply_chroma_key(image, global_settings)
        _, edge_alpha = apply_chroma_key(image, edge_settings)

        self.assertLess(int(global_alpha[50, 60]), 5)
        self.assertGreater(int(edge_alpha[50, 60]), 250)
        self.assertLess(int(edge_alpha[5, 5]), 5)

    def test_auto_mode_uses_edge_connected_for_black_background(self) -> None:
        image = np.zeros((60, 80, 3), dtype=np.uint8)
        image[10:55, 15:65] = (150, 90, 50)
        image[25:35, 35:45] = (0, 0, 0)
        settings = ChromaKeySettings(
            background_rgb=(0, 0, 0),
            tolerance=10,
            softness=6,
            cleanup_radius=0,
            edge_decontamination=0,
            keying_mode='auto',
        )
        _, alpha = apply_chroma_key(image, settings)
        self.assertGreater(int(alpha[30, 40]), 250)
        self.assertLess(int(alpha[2, 2]), 5)


if __name__ == '__main__':
    unittest.main()
