from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.generation.wan_contract import (
    builtin_resolution_options,
    load_custom_resolution_options,
    merged_resolution_options,
    normalize_wan_frame_count,
    option_for_selection,
    read_force_fps,
    resolve_fps_contract,
    template_resolution_option,
)


class WanGenerationContractTests(unittest.TestCase):
    def test_builtin_480_landscape_matches_wangp_native_value(self) -> None:
        option = option_for_selection(builtin_resolution_options(), '480p', '16:9')
        self.assertIsNotNone(option)
        self.assertEqual(option.value, '832x480')  # type: ignore[union-attr]

    def test_builtin_360_square_and_portrait_match_validation_values(self) -> None:
        square = option_for_selection(builtin_resolution_options(), '360p', '1:1')
        portrait = option_for_selection(builtin_resolution_options(), '360p', '9:16')
        self.assertEqual(square.value, '448x448')  # type: ignore[union-attr]
        self.assertEqual(portrait.value, '320x576')  # type: ignore[union-attr]

    def test_frame_count_is_floored_to_four_n_plus_one(self) -> None:
        self.assertEqual(normalize_wan_frame_count(24), 21)
        self.assertEqual(normalize_wan_frame_count(49), 49)
        self.assertEqual(normalize_wan_frame_count(81), 81)

    def test_custom_resolutions_json_overrides_matching_class_and_ratio(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / 'resolutions.json').write_text(
                json.dumps([
                    ['Custom 832x480 (16:9, 480p)', '832x480'],
                    ['Custom 640x640 (1:1, 480p)', '640x640'],
                    ['Invalid not multiple of 16 (1:1, 480p)', '650x650'],
                ]),
                encoding='utf-8',
            )
            options = load_custom_resolution_options(root)
            self.assertEqual([option.value for option in options], ['832x480', '640x640'])
            merged = merged_resolution_options(root)
            square = option_for_selection(merged, '480p', '1:1')
            self.assertEqual(square.value, '640x640')  # type: ignore[union-attr]
            self.assertTrue(square.source.endswith('resolutions.json'))  # type: ignore[union-attr]

    def test_template_resolution_is_read_and_preserved(self) -> None:
        with TemporaryDirectory() as temp_dir:
            template = Path(temp_dir) / 'preset.json'
            template.write_text(
                json.dumps({'resolution': '832x480', 'force_fps': 'control'}),
                encoding='utf-8',
            )
            option = template_resolution_option(template)
            self.assertEqual(option.value, '832x480')  # type: ignore[union-attr]
            self.assertEqual(read_force_fps(template), 'control')

    def test_control_fps_uses_motion_reference_rate(self) -> None:
        contract = resolve_fps_contract(12.0, 'control', 24.0)
        self.assertEqual(contract.effective_fps, 24.0)
        self.assertEqual(contract.source, 'control_video')

    def test_numeric_force_fps_overrides_requested_rate(self) -> None:
        contract = resolve_fps_contract(12.0, '16', 24.0)
        self.assertEqual(contract.effective_fps, 16.0)
        self.assertEqual(contract.source, 'preset_force_fps')

    def test_empty_force_fps_uses_requested_rate(self) -> None:
        contract = resolve_fps_contract(12.0, '', 24.0)
        self.assertEqual(contract.effective_fps, 12.0)
        self.assertEqual(contract.source, 'request')


if __name__ == '__main__':
    unittest.main()
