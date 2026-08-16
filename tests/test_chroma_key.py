from __future__ import annotations

import unittest

import numpy as np

from app.chroma_key import (
    apply_chroma_key,
    auto_detect_background_rgb,
    crop_rgba_to_subject,
    _decontaminate_edges,
    _decontaminate_edges_multi,
    create_alpha_mask,
    create_alpha_mask_with_diagnostics,
)
from app.models import BackgroundColorRule, ChromaKeySettings


class ChromaKeyTests(unittest.TestCase):
    def make_test_image(self) -> np.ndarray:
        image = np.zeros((100, 120, 3), dtype=np.uint8)
        image[:] = (10, 240, 20)
        image[25:75, 40:85] = (210, 40, 35)
        return image

    def test_auto_detect_background_uses_corners(self) -> None:
        image = self.make_test_image()
        detected = auto_detect_background_rgb(image)
        self.assertEqual(detected, (10, 240, 20))

    def test_key_separates_subject_from_background(self) -> None:
        image = self.make_test_image()
        settings = ChromaKeySettings(
            background_rgb=(10, 240, 20),
            tolerance=18,
            softness=10,
            cleanup_radius=0,
            edge_decontamination=0,
        )
        rgba, alpha = apply_chroma_key(image, settings)
        self.assertLess(int(alpha[5, 5]), 5)
        self.assertGreater(int(alpha[50, 60]), 250)
        self.assertEqual(rgba.shape, (100, 120, 4))

    def test_crop_contains_subject_with_padding(self) -> None:
        image = self.make_test_image()
        settings = ChromaKeySettings(
            background_rgb=(10, 240, 20),
            tolerance=18,
            softness=0,
            cleanup_radius=0,
            edge_decontamination=0,
        )
        rgba, _ = apply_chroma_key(image, settings)
        cropped, box = crop_rgba_to_subject(rgba, padding=3)
        self.assertEqual(box, (37, 22, 88, 78))
        self.assertEqual(cropped.shape[:2], (56, 51))

    def test_additional_background_colors_union(self) -> None:
        image = np.zeros((60, 90, 3), dtype=np.uint8)
        image[:, :30] = (0, 255, 0)
        image[:, 30:60] = (90, 20, 110)
        image[:, 60:] = (220, 40, 30)
        settings = ChromaKeySettings(
            background_rgb=(0, 255, 0),
            tolerance=4,
            softness=0,
            cleanup_radius=0,
            edge_decontamination=0,
            keying_mode='global',
            additional_background_colors=[BackgroundColorRule(rgb=(90, 20, 110))],
        )
        _rgba, alpha = apply_chroma_key(image, settings)
        self.assertEqual(int(alpha[10, 10]), 0)
        self.assertEqual(int(alpha[10, 40]), 0)
        self.assertEqual(int(alpha[10, 75]), 255)

    def test_disabled_additional_color_is_pixel_identical_to_legacy(self) -> None:
        image = self.make_test_image()
        legacy = ChromaKeySettings(
            background_rgb=(10, 240, 20), tolerance=18, softness=10, cleanup_radius=1, edge_decontamination=60, keying_mode='global'
        )
        extended = ChromaKeySettings(
            background_rgb=(10, 240, 20), tolerance=18, softness=10, cleanup_radius=1, edge_decontamination=60, keying_mode='global',
            additional_background_colors=[BackgroundColorRule(rgb=(100, 20, 100), enabled=False, tolerance=80)],
        )
        rgba_legacy, alpha_legacy = apply_chroma_key(image, legacy)
        rgba_extended, alpha_extended = apply_chroma_key(image, extended)
        self.assertTrue(np.array_equal(alpha_legacy, alpha_extended))
        self.assertTrue(np.array_equal(rgba_legacy, rgba_extended))

    def test_additional_color_local_tolerance_overrides_global(self) -> None:
        image = np.zeros((20, 40, 3), dtype=np.uint8)
        image[:, :20] = (110, 25, 105)
        image[:, 20:] = (220, 40, 30)
        strict = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=0, softness=0, cleanup_radius=0, edge_decontamination=0, keying_mode='global',
            additional_background_colors=[BackgroundColorRule(rgb=(100, 20, 100), tolerance=0)],
        )
        tolerant = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=0, softness=0, cleanup_radius=0, edge_decontamination=0, keying_mode='global',
            additional_background_colors=[BackgroundColorRule(rgb=(100, 20, 100), tolerance=12)],
        )
        _rgba_strict, alpha_strict = apply_chroma_key(image, strict)
        _rgba_tolerant, alpha_tolerant = apply_chroma_key(image, tolerant)
        self.assertEqual(int(alpha_strict[5, 5]), 255)
        self.assertEqual(int(alpha_tolerant[5, 5]), 0)
        self.assertEqual(int(alpha_tolerant[5, 30]), 255)

    def test_additional_colors_work_with_edge_connected(self) -> None:
        image = np.zeros((40, 60, 3), dtype=np.uint8)
        image[:] = (200, 30, 20)
        image[:, :8] = (0, 255, 0)
        image[:, -8:] = (90, 20, 110)
        # An enclosed purple detail must survive edge-connected mode.
        image[15:25, 25:35] = (90, 20, 110)
        settings = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=3, softness=0, cleanup_radius=0, edge_decontamination=0, keying_mode='edge_connected',
            additional_background_colors=[BackgroundColorRule(rgb=(90, 20, 110), tolerance=3)],
        )
        _rgba, alpha = apply_chroma_key(image, settings)
        self.assertEqual(int(alpha[5, 2]), 0)
        self.assertEqual(int(alpha[5, 57]), 0)
        self.assertEqual(int(alpha[20, 30]), 255)

    def test_multicolor_decontamination_uses_nearest_background(self) -> None:
        image = np.array([[[20, 180, 20], [100, 25, 110]]], dtype=np.uint8)
        alpha = np.array([[128, 128]], dtype=np.uint8)
        settings = ChromaKeySettings(
            background_rgb=(0, 255, 0),
            edge_decontamination=100,
            additional_background_colors=[BackgroundColorRule(rgb=(90, 20, 110), enabled=True)],
        )
        corrected = _decontaminate_edges_multi(image, alpha, settings)
        expected_green = _decontaminate_edges(image[:, :1], alpha[:, :1], (0, 255, 0), 100)
        expected_purple = _decontaminate_edges(image[:, 1:], alpha[:, 1:], (90, 20, 110), 100)
        self.assertTrue(np.array_equal(corrected[:, :1], expected_green))
        self.assertTrue(np.array_equal(corrected[:, 1:], expected_purple))

    def test_chroma_settings_serializes_additional_colors(self) -> None:
        settings = ChromaKeySettings(
            additional_background_colors=[
                BackgroundColorRule(rgb=(1, 2, 3), enabled=True, tolerance=None),
                BackgroundColorRule(rgb=(4, 5, 6), enabled=False, tolerance=22),
            ]
        )
        payload = settings.to_dict()
        self.assertEqual(payload['additional_background_colors'][0]['rgb'], [1, 2, 3])
        self.assertIsNone(payload['additional_background_colors'][0]['tolerance'])
        self.assertFalse(payload['additional_background_colors'][1]['enabled'])
        self.assertEqual(payload['additional_background_colors'][1]['tolerance'], 22)

    def test_outer_border_mask_10px(self) -> None:
        image = np.zeros((80, 100, 3), dtype=np.uint8)
        image[:] = (200, 30, 20)
        settings = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=0, softness=0, cleanup_radius=0, edge_decontamination=0,
            keying_mode='global', outer_border_mask_px=10,
        )
        alpha = create_alpha_mask(image, settings)
        self.assertTrue(np.all(alpha[:10, :] == 0))
        self.assertTrue(np.all(alpha[-10:, :] == 0))
        self.assertTrue(np.all(alpha[:, :10] == 0))
        self.assertTrue(np.all(alpha[:, -10:] == 0))
        self.assertTrue(np.all(alpha[10:-10, 10:-10] == 255))

    def test_outer_border_zero_is_pixel_identical(self) -> None:
        image = self.make_test_image()
        base = ChromaKeySettings(
            background_rgb=(10, 240, 20), tolerance=18, softness=10, cleanup_radius=1, edge_decontamination=60,
            keying_mode='edge_connected',
            additional_background_colors=[BackgroundColorRule(rgb=(12, 220, 30), tolerance=7)],
        )
        structural_zero = ChromaKeySettings(
            background_rgb=(10, 240, 20), tolerance=18, softness=10, cleanup_radius=1, edge_decontamination=60,
            keying_mode='edge_connected',
            additional_background_colors=[BackgroundColorRule(rgb=(12, 220, 30), tolerance=7)],
            outer_border_mask_px=0, subject_edge_mask_expand_px=0,
        )
        rgba_a, alpha_a = apply_chroma_key(image, base)
        rgba_b, alpha_b = apply_chroma_key(image, structural_zero)
        self.assertTrue(np.array_equal(alpha_a, alpha_b))
        self.assertTrue(np.array_equal(rgba_a, rgba_b))

    def test_subject_component_detection_prefers_center(self) -> None:
        image = np.zeros((100, 120, 3), dtype=np.uint8)
        image[:] = (0, 255, 0)
        image[25:85, 45:80] = (220, 40, 30)
        image[2:12, 2:12] = (220, 40, 30)
        settings = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=2, softness=0, cleanup_radius=0, edge_decontamination=0,
            keying_mode='global', subject_edge_mask_expand_px=1,
        )
        _alpha, diagnostic = create_alpha_mask_with_diagnostics(image, settings)
        self.assertTrue(diagnostic.subject_detected)
        self.assertGreater(int(diagnostic.subject_mask[50, 60]), 0)
        self.assertEqual(int(diagnostic.subject_mask[5, 5]), 0)

    def test_subject_edge_expand_2px_erodes_detected_subject(self) -> None:
        image = np.zeros((80, 80, 3), dtype=np.uint8)
        image[:] = (0, 255, 0)
        image[20:60, 20:60] = (220, 40, 30)
        base = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=2, softness=0, cleanup_radius=0, edge_decontamination=0, keying_mode='global'
        )
        refined = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=2, softness=0, cleanup_radius=0, edge_decontamination=0, keying_mode='global',
            subject_edge_mask_expand_px=2,
        )
        alpha_base = create_alpha_mask(image, base)
        alpha_refined, diagnostic = create_alpha_mask_with_diagnostics(image, refined)
        self.assertTrue(diagnostic.subject_detected)
        self.assertEqual(int(alpha_base[20, 40]), 255)
        self.assertEqual(int(alpha_refined[20, 40]), 0)
        self.assertEqual(int(alpha_refined[22, 40]), 255)
        self.assertEqual(int(alpha_refined[40, 40]), 255)

    def test_subject_not_detected_is_safe(self) -> None:
        image = np.zeros((60, 60, 3), dtype=np.uint8)
        image[:] = (0, 255, 0)
        settings = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=2, softness=0, cleanup_radius=0, edge_decontamination=0, keying_mode='global',
            subject_edge_mask_expand_px=3,
        )
        alpha, diagnostic = create_alpha_mask_with_diagnostics(image, settings)
        self.assertFalse(diagnostic.subject_detected)
        self.assertEqual(diagnostic.subject_edge_mask_expand_px, 0)
        self.assertTrue(np.all(alpha == 0))

    def test_edge_connected_outer_border_acts_as_seed(self) -> None:
        image = np.zeros((40, 60, 3), dtype=np.uint8)
        image[:] = (220, 40, 30)
        # Background-colored region starts inside a forced 4 px strip and extends inward.
        image[5:35, 2:15] = (0, 255, 0)
        settings = ChromaKeySettings(
            background_rgb=(0, 255, 0), tolerance=2, softness=0, cleanup_radius=0, edge_decontamination=0,
            keying_mode='edge_connected', outer_border_mask_px=4,
        )
        alpha = create_alpha_mask(image, settings)
        self.assertEqual(int(alpha[20, 10]), 0)
        self.assertEqual(int(alpha[20, 30]), 255)

    def test_structural_settings_are_serialized(self) -> None:
        settings = ChromaKeySettings(outer_border_mask_px=12, subject_edge_mask_expand_px=3)
        payload = settings.to_dict()
        self.assertEqual(payload['outer_border_mask_px'], 12)
        self.assertEqual(payload['subject_edge_mask_expand_px'], 3)


if __name__ == "__main__":
    unittest.main()
