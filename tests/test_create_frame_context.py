from __future__ import annotations

import unittest

from app.create_frame_context import CreateFrameContext, normalize_onion_skin_mode


class CreateFrameContextTests(unittest.TestCase):
    def test_empty_context_is_valid(self) -> None:
        context = CreateFrameContext()
        self.assertFalse(context.has_frames)
        self.assertIsNone(context.current_frame_index)
        self.assertEqual(context.selected_frames, ())
        self.assertIsNone(context.onion_target_index('off'))

    def test_context_normalizes_selection_and_exposes_timing(self) -> None:
        context = CreateFrameContext(
            frame_count=12,
            current_frame_index=4,
            selected_frames=(7, 2, 7, 4),
            fps=24.0,
            source_kind='video',
            source_label='walk.mp4',
        )
        self.assertEqual(context.selected_frames, (2, 4, 7))
        self.assertEqual(context.selection_count, 3)
        self.assertAlmostEqual(context.frame_time_seconds(), 4 / 24.0)
        self.assertEqual(context.source_label, 'walk.mp4')

    def test_out_of_range_context_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CreateFrameContext(frame_count=-1)
        with self.assertRaises(ValueError):
            CreateFrameContext(frame_count=3, current_frame_index=3)
        with self.assertRaises(ValueError):
            CreateFrameContext(frame_count=3, selected_frames=(0, 3))
        with self.assertRaises(ValueError):
            CreateFrameContext(frame_count=3, fps=0)

    def test_onion_target_is_explicit_and_bounded(self) -> None:
        first = CreateFrameContext(frame_count=5, current_frame_index=0, fps=12)
        middle = CreateFrameContext(frame_count=5, current_frame_index=2, fps=12)
        last = CreateFrameContext(frame_count=5, current_frame_index=4, fps=12)
        self.assertIsNone(first.onion_target_index('previous'))
        self.assertEqual(first.onion_target_index('next'), 1)
        self.assertEqual(middle.onion_target_index('previous'), 1)
        self.assertEqual(middle.onion_target_index('next'), 3)
        self.assertEqual(last.onion_target_index('previous'), 3)
        self.assertIsNone(last.onion_target_index('next'))
        self.assertIsNone(middle.onion_target_index('off'))

    def test_unknown_onion_mode_is_rejected(self) -> None:
        self.assertEqual(normalize_onion_skin_mode(None), 'off')
        with self.assertRaises(ValueError):
            normalize_onion_skin_mode('both')


if __name__ == '__main__':
    unittest.main()
