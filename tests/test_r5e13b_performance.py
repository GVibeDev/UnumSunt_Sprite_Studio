from __future__ import annotations

import ast
import unittest
from pathlib import Path

import numpy as np

from app.alpha_cleanup import paint_alpha_circle, paint_alpha_circle_inplace
from app.chroma_key import render_checkerboard, render_checkerboard_region


ROOT = Path(__file__).resolve().parents[1]


def _legacy_paint_alpha_circle(
    rgba: np.ndarray,
    center_x: float,
    center_y: float,
    radius: int,
    mode: str,
) -> np.ndarray:
    result = rgba.copy()
    h, w = rgba.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    mask = (xx - float(center_x)) ** 2 + (yy - float(center_y)) ** 2 <= max(1, int(radius)) ** 2
    if mode == 'erase':
        result[mask, 3] = 0
        result[mask, :3] = 0
    elif mode == 'restore':
        original = rgba[mask]
        result[mask, 3] = 255
        restore_mask = np.all(original[:, :3] == 0, axis=1)
        if np.any(~restore_mask):
            result_pixels = result[mask]
            result_pixels[~restore_mask, :3] = original[~restore_mask, :3]
            result[mask] = result_pixels
    else:
        raise ValueError(mode)
    return result


class R5e13bPerformanceTests(unittest.TestCase):
    def test_roi_painter_is_pixel_identical_to_r5e13a_algorithm(self) -> None:
        rng = np.random.default_rng(513)
        rgba = rng.integers(0, 256, size=(73, 91, 4), dtype=np.uint8)
        cases = [
            (0.1, 0.2, 1),
            (45.5, 36.25, 5),
            (90.8, 72.7, 12),
            (17.2, 60.4, 3),
        ]
        for mode in ('erase', 'restore'):
            for x, y, radius in cases:
                with self.subTest(mode=mode, x=x, y=y, radius=radius):
                    expected = _legacy_paint_alpha_circle(rgba, x, y, radius, mode)
                    actual = paint_alpha_circle(rgba, x, y, radius, mode)
                    self.assertTrue(np.array_equal(actual, expected))

    def test_inplace_painter_limits_work_to_brush_roi(self) -> None:
        rgba = np.full((2048, 2048, 4), 255, dtype=np.uint8)
        region = paint_alpha_circle_inplace(rgba, 1024.25, 1023.75, 6, 'erase')
        self.assertTrue(region.changed)
        self.assertLessEqual(region.width, 15)
        self.assertLessEqual(region.height, 15)
        self.assertEqual(int(rgba[0, 0, 3]), 255)
        self.assertEqual(int(rgba[1024, 1024, 3]), 0)

    def test_checkerboard_region_matches_full_frame_slice_exactly(self) -> None:
        rng = np.random.default_rng(1313)
        rgba = rng.integers(0, 256, size=(81, 97, 4), dtype=np.uint8)
        full = render_checkerboard(rgba, tile_size=14)
        left, top, right, bottom = 19, 23, 46, 57
        region = render_checkerboard_region(
            rgba[top:bottom, left:right],
            origin_x=left,
            origin_y=top,
            tile_size=14,
        )
        self.assertTrue(np.array_equal(region, full[top:bottom, left:right]))

    def test_cleanup_studio_uses_stroke_lifecycle_and_single_commit_boundary(self) -> None:
        source = (ROOT / 'app' / 'cleanup_studio.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'CleanupStudio')
        methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
        self.assertIn('_begin_brush_stroke', methods)
        self.assertIn('_paint_brush', methods)
        self.assertIn('_end_brush_stroke', methods)
        paint_calls = [
            node for node in ast.walk(methods['_paint_brush'])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == '_commit_transaction'
        ]
        end_calls = [
            node for node in ast.walk(methods['_end_brush_stroke'])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == '_commit_transaction'
        ]
        self.assertEqual(len(paint_calls), 0)
        self.assertEqual(len(end_calls), 1)

    def test_cleanup_canvas_exposes_dirty_region_update(self) -> None:
        source = (ROOT / 'app' / 'cleanup_canvas.py').read_text(encoding='utf-8')
        self.assertIn('def update_image_region(', source)
        self.assertIn('brush_stroke_started = Signal', source)
        self.assertIn('brush_stroke_finished = Signal', source)
        self.assertNotIn(').copy()\n            painter.drawImage', source)


if __name__ == '__main__':
    unittest.main()
