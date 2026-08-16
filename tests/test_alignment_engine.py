from __future__ import annotations

import unittest

import numpy as np

from app.alignment_engine import (
    SubjectFrame,
    calculate_shared_fit_scale,
    create_spritesheet,
    estimate_ground_pivot,
    render_aligned_frame,
)
from app.models import AlignmentSettings, FrameAlignmentState


class AlignmentEngineTests(unittest.TestCase):
    def make_subject(self, frame_index: int = 0) -> SubjectFrame:
        rgba = np.zeros((40, 30, 4), dtype=np.uint8)
        rgba[5:40, 5:25, :3] = (180, 90, 40)
        rgba[5:40, 5:25, 3] = 255
        pivot_x, pivot_y = estimate_ground_pivot(rgba)
        return SubjectFrame(
            frame_index=frame_index,
            rgba=rgba,
            crop_box=(10, 20, 40, 60),
            auto_pivot_x=pivot_x,
            auto_pivot_y=pivot_y,
        )

    def test_ground_pivot_is_at_bottom_center(self) -> None:
        subject = self.make_subject()
        self.assertAlmostEqual(subject.auto_pivot_x, 14.5, places=1)
        self.assertEqual(subject.auto_pivot_y, 40.0)

    def test_shared_fit_scale_keeps_subject_inside_canvas(self) -> None:
        subject = self.make_subject()
        state = FrameAlignmentState(
            frame_index=0,
            source_pivot_x=subject.auto_pivot_x,
            source_pivot_y=subject.auto_pivot_y,
        )
        settings = AlignmentSettings(
            canvas_width=96,
            canvas_height=96,
            canvas_pivot_x=48,
            canvas_pivot_y=88,
            margin=4,
        )
        scale = calculate_shared_fit_scale(
            {0: subject},
            {0: state},
            settings,
        )
        self.assertGreater(scale, 0)
        settings.shared_scale = scale
        rendered, placement = render_aligned_frame(
            subject,
            state,
            settings,
        )
        self.assertEqual(rendered.shape, (96, 96, 4))
        ys, xs = np.nonzero(rendered[:, :, 3] > 8)
        self.assertGreater(len(xs), 0)
        self.assertLessEqual(int(xs.max()), 91)
        self.assertLessEqual(int(ys.max()), 87)

    def test_render_places_ground_at_canvas_pivot(self) -> None:
        subject = self.make_subject()
        state = FrameAlignmentState(
            frame_index=0,
            source_pivot_x=subject.auto_pivot_x,
            source_pivot_y=subject.auto_pivot_y,
        )
        settings = AlignmentSettings(
            canvas_width=96,
            canvas_height=96,
            canvas_pivot_x=48,
            canvas_pivot_y=88,
            margin=0,
            shared_scale=1.0,
        )
        rendered, _ = render_aligned_frame(
            subject,
            state,
            settings,
        )
        ys, _ = np.nonzero(rendered[:, :, 3] > 8)
        self.assertEqual(int(ys.max()), 87)

    def test_spritesheet_grid_dimensions(self) -> None:
        frames = [
            np.zeros((96, 96, 4), dtype=np.uint8)
            for _ in range(5)
        ]
        sheet, positions, columns, rows = create_spritesheet(
            frames,
            layout="grid",
            columns=3,
            padding=2,
        )
        self.assertEqual(columns, 3)
        self.assertEqual(rows, 2)
        self.assertEqual(sheet.shape, (194, 292, 4))
        self.assertEqual(len(positions), 5)


if __name__ == "__main__":
    unittest.main()
