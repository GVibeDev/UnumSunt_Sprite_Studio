from __future__ import annotations

import unittest

import numpy as np

from app.frame_analysis import (
    analyze_and_select,
    extract_frame_feature,
    feature_distance,
    sensitivity_to_duplicate_threshold,
)
from app.models import ChromaKeySettings


class FrameAnalysisTests(unittest.TestCase):
    def make_frame(
        self,
        *,
        x: int,
        width: int = 24,
        height: int = 50,
        arm_offset: int = 0,
    ) -> np.ndarray:
        image = np.zeros((120, 140, 3), dtype=np.uint8)
        image[:] = (0, 255, 0)
        left = x
        top = 55
        image[top : top + height, left : left + width] = (160, 80, 45)
        arm_x = max(0, min(139, left + width + arm_offset))
        image[70:82, arm_x : min(140, arm_x + 8)] = (160, 80, 45)
        return image

    def feature(self, index: int, frame: np.ndarray):
        return extract_frame_feature(
            frame_index=index,
            time_seconds=index / 25.0,
            image_rgb=frame,
            chroma_settings=ChromaKeySettings(
                background_rgb=(0, 255, 0),
                tolerance=18,
                softness=0,
                cleanup_radius=0,
                edge_decontamination=0,
            ),
        )

    def test_identical_frames_have_near_zero_distance(self) -> None:
        first = self.feature(0, self.make_frame(x=40))
        second = self.feature(1, self.make_frame(x=40))
        self.assertLess(feature_distance(first, second), 0.001)

    def test_motion_increases_feature_distance(self) -> None:
        first = self.feature(0, self.make_frame(x=38, arm_offset=-2))
        second = self.feature(1, self.make_frame(x=44, arm_offset=7))
        self.assertGreater(feature_distance(first, second), 0.01)

    def test_walk_selection_returns_requested_count_in_order(self) -> None:
        features = [
            self.feature(
                index,
                self.make_frame(
                    x=38 + (index % 3),
                    arm_offset=(index % 5) - 2,
                ),
            )
            for index in range(12)
        ]
        result = analyze_and_select(
            features=features,
            profile="walk",
            desired_count=8,
            duplicate_threshold=0.018,
        )
        self.assertEqual(len(result.suggestions), 8)
        self.assertEqual(result.suggestions, sorted(result.suggestions))
        self.assertTrue(all(0 <= index < 12 for index in result.suggestions))

    def test_interact_selection_preserves_temporal_coverage(self) -> None:
        features = [
            self.feature(
                index,
                self.make_frame(
                    x=40,
                    width=24 + (index // 3),
                    arm_offset=index,
                ),
            )
            for index in range(10)
        ]
        result = analyze_and_select(
            features=features,
            profile="interact",
            desired_count=5,
            duplicate_threshold=0.012,
        )
        self.assertEqual(len(result.suggestions), 5)
        self.assertEqual(result.suggestions[0], 0)
        self.assertEqual(result.suggestions[-1], 9)

    def test_duplicate_detection_flags_repeated_frame(self) -> None:
        frames = [
            self.make_frame(x=40, arm_offset=0),
            self.make_frame(x=40, arm_offset=0),
            self.make_frame(x=42, arm_offset=6),
        ]
        features = [
            self.feature(index, frame)
            for index, frame in enumerate(frames)
        ]
        result = analyze_and_select(
            features=features,
            profile="idle",
            desired_count=2,
            duplicate_threshold=0.02,
        )
        self.assertGreaterEqual(len(result.duplicate_pairs), 1)
        self.assertIn("quasi duplicato", result.features[1].flags)

    def test_sensitivity_mapping_is_monotonic(self) -> None:
        self.assertLess(
            sensitivity_to_duplicate_threshold(0),
            sensitivity_to_duplicate_threshold(100),
        )


if __name__ == "__main__":
    unittest.main()
