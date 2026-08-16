from __future__ import annotations

import unittest

import numpy as np

from app.alignment_engine import SubjectFrame
from app.models import AlignmentSettings, FrameAlignmentState
from app.output_geometry import (
    MAX_OUTPUT_DIMENSION,
    MIN_OUTPUT_DIMENSION,
    OUTPUT_SIZE_PRESETS,
    analyze_canvas_geometry,
    locked_size_from_height,
    locked_size_from_width,
    migrate_canvas_pivot,
    preset_for_size,
    validate_output_size,
)


class OutputGeometryTests(unittest.TestCase):
    def _subject(self) -> SubjectFrame:
        rgba = np.zeros((40, 20, 4), dtype=np.uint8)
        rgba[:, :, 3] = 255
        return SubjectFrame(
            frame_index=0,
            rgba=rgba,
            crop_box=(0, 0, 20, 40),
            auto_pivot_x=10,
            auto_pivot_y=40,
        )

    def test_supported_range_and_rectangular_presets(self) -> None:
        self.assertEqual(validate_output_size(36, 256), (36, 256))
        self.assertEqual(validate_output_size(256, 36), (256, 36))
        with self.assertRaises(ValueError):
            validate_output_size(MIN_OUTPUT_DIMENSION - 1, 96)
        with self.assertRaises(ValueError):
            validate_output_size(96, MAX_OUTPUT_DIMENSION + 1)
        self.assertTrue(any(p.width == 96 and p.height == 128 for p in OUTPUT_SIZE_PRESETS))
        self.assertTrue(any(p.width == 128 and p.height == 96 for p in OUTPUT_SIZE_PRESETS))
        self.assertEqual(preset_for_size(96, 128).key, 'portrait-96x128')
        self.assertEqual(preset_for_size(101, 137).key, 'custom')

    def test_pivot_migration_proportional_and_absolute(self) -> None:
        self.assertEqual(
            migrate_canvas_pivot(96, 96, 192, 128, 48, 88, proportional=True),
            (96.0, 117.33333333333333),
        )
        self.assertEqual(
            migrate_canvas_pivot(96, 96, 64, 64, 48, 88, proportional=False),
            (48.0, 64.0),
        )

    def test_locked_aspect_calculation(self) -> None:
        self.assertEqual(locked_size_from_width(128, 4 / 3), (128, 96))
        self.assertEqual(locked_size_from_height(192, 2 / 3), (128, 192))

    def test_geometry_report_detects_clipping(self) -> None:
        subject = self._subject()
        state = FrameAlignmentState(frame_index=0, source_pivot_x=10, source_pivot_y=40)
        safe = AlignmentSettings(
            canvas_width=96,
            canvas_height=96,
            canvas_pivot_x=48,
            canvas_pivot_y=88,
            margin=4,
            shared_scale=1.0,
        )
        report = analyze_canvas_geometry({0: subject}, {0: state}, safe)
        self.assertTrue(report.is_safe)
        clipped = AlignmentSettings(
            canvas_width=36,
            canvas_height=36,
            canvas_pivot_x=18,
            canvas_pivot_y=18,
            margin=0,
            shared_scale=2.0,
        )
        clipped_report = analyze_canvas_geometry({0: subject}, {0: state}, clipped)
        self.assertFalse(clipped_report.is_safe)
        self.assertEqual(clipped_report.clipped_frames, (0,))
        self.assertGreater(sum(clipped_report.maximum_overflow), 0)


if __name__ == '__main__':
    unittest.main()
