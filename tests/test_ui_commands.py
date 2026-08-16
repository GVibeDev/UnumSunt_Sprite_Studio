from __future__ import annotations

import unittest

from app.ui_commands import (
    TAB_ROUTES,
    TAB_SHORT_LABELS,
    TAB_TOOLTIPS,
    tab_gradient_colors,
    toolbar_command_state,
)


class UiCommandTests(unittest.TestCase):
    def test_tab_metadata_remains_aligned(self) -> None:
        self.assertEqual(len(TAB_ROUTES), 14)
        self.assertEqual(len(TAB_ROUTES), len(TAB_SHORT_LABELS))
        self.assertEqual(len(TAB_ROUTES), len(TAB_TOOLTIPS))
        self.assertEqual(len(set(TAB_ROUTES)), len(TAB_ROUTES))

    def test_extraction_video_controls_are_contextual(self) -> None:
        self.assertEqual(toolbar_command_state('play', 'extraction', video_open=True), (True, True))
        self.assertEqual(toolbar_command_state('play', 'generation', video_open=True), (False, False))
        self.assertEqual(toolbar_command_state('play', 'extraction', video_open=False), (True, False))

    def test_open_video_does_not_pollute_unrelated_tools(self) -> None:
        self.assertEqual(toolbar_command_state('open_video', 'generation', video_open=False), (True, True))
        self.assertEqual(toolbar_command_state('open_video', 'production_presets', video_open=False), (False, False))
        self.assertEqual(toolbar_command_state('open_video', 'image_generation', video_open=False), (False, False))

    def test_gradient_is_monotonic_lighter(self) -> None:
        colors = tab_gradient_colors(14)
        self.assertEqual(len(colors), 14)
        luminance = [sum(color) for color in colors]
        self.assertEqual(luminance, sorted(luminance))
        self.assertNotEqual(colors[0], colors[-1])


if __name__ == '__main__':
    unittest.main()
