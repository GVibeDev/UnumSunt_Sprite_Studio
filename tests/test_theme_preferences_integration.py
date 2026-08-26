from pathlib import Path
import unittest


class ThemePreferencesIntegrationTests(unittest.TestCase):
    def test_file_menu_contains_preferences(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn("'Preferences…'", source)
        self.assertIn('self.theme_preferences.open_preferences()', source)

    def test_toolbar_contains_theme_switch(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn('self.theme_switch_action', source)
        self.assertIn('self.theme_preferences.cycle()', source)

    def test_theme_is_persisted_in_app_state(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        self.assertIn('self.theme_preferences.snapshot()', source)
        self.assertIn("self.theme_preferences.restore(state.get('preferences'))", source)

    def test_status_bar_has_explicit_white_foreground(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / 'app' / 'ui_theme.py').read_text(encoding='utf-8')
        self.assertIn('QStatusBar { color: #ffffff;', source)
        self.assertIn('QStatusBar QLabel { color: #ffffff;', source)
