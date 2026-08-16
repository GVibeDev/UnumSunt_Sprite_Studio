from __future__ import annotations

import unittest

from app.ui_theme import DEFAULT_TAB_THEME, TAB_THEMES, next_theme_name, normalize_theme_name, tab_theme_colors


class UiThemeTests(unittest.TestCase):
    def test_three_selectable_app_gradients_exist(self) -> None:
        self.assertEqual(set(TAB_THEMES), {'red', 'green', 'blue'})

    def test_text_luminance_increases_while_background_decreases(self) -> None:
        for key in TAB_THEMES:
            pairs = tab_theme_colors(key, 14)
            text_luminance = [sum(text) for text, _background in pairs]
            background_luminance = [sum(background) for _text, background in pairs]
            self.assertEqual(text_luminance, sorted(text_luminance))
            self.assertEqual(background_luminance, sorted(background_luminance, reverse=True))
            self.assertNotEqual(pairs[0], pairs[-1])

    def test_theme_cycle_is_red_green_blue(self) -> None:
        self.assertEqual(next_theme_name('red'), 'green')
        self.assertEqual(next_theme_name('green'), 'blue')
        self.assertEqual(next_theme_name('blue'), 'red')

    def test_invalid_theme_falls_back_to_default(self) -> None:
        self.assertEqual(normalize_theme_name('unknown'), DEFAULT_TAB_THEME)
