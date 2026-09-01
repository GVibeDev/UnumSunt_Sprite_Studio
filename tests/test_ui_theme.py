from __future__ import annotations

import unittest

from app.ui_theme import (
    DEFAULT_WORKSTATION_THEME,
    TAB_THEMES,
    WORKSTATION_THEMES,
    next_theme_name,
    normalize_theme_name,
    tab_theme_colors,
    workstation_theme_colors,
    workstation_theme_stylesheet,
)


class UiThemeTests(unittest.TestCase):
    def test_three_selectable_workstation_accents_exist(self) -> None:
        self.assertEqual(set(WORKSTATION_THEMES), {'red', 'green', 'blue'})

    def test_legacy_theme_registry_alias_remains_compatible(self) -> None:
        self.assertIs(TAB_THEMES, WORKSTATION_THEMES)

    def test_text_luminance_increases_while_background_decreases(self) -> None:
        for key in WORKSTATION_THEMES:
            pairs = workstation_theme_colors(key, 14)
            text_luminance = [sum(text) for text, _background in pairs]
            background_luminance = [sum(background) for _text, background in pairs]
            self.assertEqual(text_luminance, sorted(text_luminance))
            self.assertEqual(background_luminance, sorted(background_luminance, reverse=True))
            self.assertNotEqual(pairs[0], pairs[-1])

    def test_legacy_color_function_delegates_to_workstation_theme(self) -> None:
        self.assertEqual(tab_theme_colors('green', 7), workstation_theme_colors('green', 7))

    def test_theme_cycle_is_red_green_blue(self) -> None:
        self.assertEqual(next_theme_name('red'), 'green')
        self.assertEqual(next_theme_name('green'), 'blue')
        self.assertEqual(next_theme_name('blue'), 'red')

    def test_invalid_theme_falls_back_to_default(self) -> None:
        self.assertEqual(normalize_theme_name('unknown'), DEFAULT_WORKSTATION_THEME)

    def test_workstation_stylesheet_targets_macro_and_route_controls(self) -> None:
        stylesheet = workstation_theme_stylesheet('blue')
        self.assertIn('workstationRole="macro"', stylesheet)
        self.assertIn('workstationRole="route"', stylesheet)
        self.assertIn(':checked', stylesheet)


if __name__ == '__main__':
    unittest.main()
