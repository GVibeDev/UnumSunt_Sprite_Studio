from pathlib import Path
import unittest


class ThemePreferencesIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.main_source = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        cls.controller_source = (root / 'app' / 'theme_preferences_controller.py').read_text(encoding='utf-8')
        cls.dialog_source = (root / 'app' / 'preferences_dialog.py').read_text(encoding='utf-8')
        cls.theme_source = (root / 'app' / 'ui_theme.py').read_text(encoding='utf-8')

    def test_file_menu_contains_preferences(self) -> None:
        self.assertIn("'Preferences…'", self.main_source)
        self.assertIn('self.theme_preferences.open_preferences()', self.main_source)

    def test_toolbar_contains_theme_switch(self) -> None:
        self.assertIn('self.theme_switch_action', self.main_source)
        self.assertIn('self.theme_preferences.cycle()', self.main_source)
        self.assertIn('workstation accent', self.main_source)

    def test_theme_controller_targets_workstation_shell(self) -> None:
        self.assertIn('workstation_provider=lambda: self.workstation_shell', self.main_source)
        self.assertNotIn('tab_bar_provider=', self.main_source)
        self.assertIn("getattr(workstation, 'apply_theme', None)", self.controller_source)

    def test_theme_is_persisted_with_workstation_key(self) -> None:
        self.assertIn("return {'workstation_theme': self.theme_name}", self.controller_source)
        self.assertIn("value.get('tab_theme'", self.controller_source)
        self.assertIn('self.theme_preferences.snapshot()', self.main_source)
        self.assertIn("self.theme_preferences.restore(state.get('preferences'))", self.main_source)

    def test_preferences_copy_no_longer_describes_fourteen_tabs(self) -> None:
        self.assertIn('GENERATE / CREATE / MANAGE', self.dialog_source)
        self.assertIn('Workstation accent', self.dialog_source)
        self.assertNotIn('14 main tabs', self.dialog_source)
        self.assertNotIn('Tab gradient', self.dialog_source)

    def test_status_bar_has_explicit_white_foreground(self) -> None:
        self.assertIn('QStatusBar { color: #ffffff;', self.theme_source)
        self.assertIn('QStatusBar QLabel { color: #ffffff;', self.theme_source)
