from __future__ import annotations

from pathlib import Path
import unittest

from PIL import Image

from app.version import APP_VERSION, WINDOWS_PRODUCT_VERSION


class R5c8InternationalReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_release_identity_is_r5c8(self) -> None:
        self.assertEqual(APP_VERSION, 'R5c8')
        self.assertEqual(WINDOWS_PRODUCT_VERSION, '5.8.0.0')

    def test_main_ui_has_english_navigation_and_help(self) -> None:
        source = (self.root / 'app' / 'main_window.py').read_text(encoding='utf-8')
        for token in ("'Preferences…'", "menu_bar.addMenu('Help')", "'Quick Start…'", "'AI Runtime Manager…'"):
            self.assertIn(token, source)
        for legacy in ("'Preferenze…'", "'Progetto'", "'Riproduci'", "'Gestione runtime AI…'"):
            self.assertNotIn(legacy, source)

    def test_built_in_help_covers_public_workflow(self) -> None:
        source = (self.root / 'app' / 'help_dialog.py').read_text(encoding='utf-8')
        for section in ('Quick Start', 'Production Workflow', 'Local AI', 'Controls & Tips', 'About & Licensing'):
            self.assertIn(section, source)
        self.assertIn('More control, not more promises.', source)

    def test_installer_is_english_and_uses_gpl_information_page(self) -> None:
        source = (self.root / 'installer' / 'UnumSuntSpriteStudio_R5c8.iss').read_text(encoding='utf-8')
        self.assertIn('#define MyAppVersion "R5c8"', source)
        self.assertIn('VersionInfoVersion=5.8.0.0', source)
        self.assertIn('Name: "english"; MessagesFile: "compiler:Default.isl"', source)
        self.assertNotIn('Languages\\Italian.isl', source)
        self.assertIn('InfoBeforeFile=..\\OPEN_SOURCE_LICENSE_NOTICE.txt', source)
        self.assertNotIn('LicenseFile=..\\LICENSE', source)
        self.assertIn('SetupIconFile=..\\assets\\branding\\app_icon.ico', source)

    def test_open_source_notice_is_bundled_with_core(self) -> None:
        notice = (self.root / 'OPEN_SOURCE_LICENSE_NOTICE.txt').read_text(encoding='utf-8')
        spec = (self.root / 'UnumSuntSpriteStudio.spec').read_text(encoding='utf-8')
        self.assertIn('GPL-3.0-or-later', notice)
        self.assertIn('Corresponding Source', notice)
        self.assertIn("('OPEN_SOURCE_LICENSE_NOTICE.txt', '.')", spec)

    def test_windows_icon_is_multiresolution(self) -> None:
        icon_path = self.root / 'assets' / 'branding' / 'app_icon.ico'
        with Image.open(icon_path) as icon:
            sizes = set(icon.info.get('sizes', set()))
        for required in ((16, 16), (32, 32), (48, 48), (256, 256)):
            self.assertIn(required, sizes)

    def test_r5c8_public_release_helpers_are_wired(self) -> None:
        prepare = (self.root / 'tools' / 'prepare_public_release.ps1').read_text(encoding='utf-8')
        setup = (self.root / 'build_setup_windows.ps1').read_text(encoding='utf-8')
        self.assertIn("$Version = 'R5c8'", prepare)
        self.assertIn('UnumSunt_Sprite_Studio_R5c8_Source.zip', prepare)
        self.assertIn('installer\\UnumSuntSpriteStudio_R5c8.iss', setup)
        self.assertTrue((self.root / 'PREPARE_PUBLIC_RELEASE_R5C8.bat').is_file())
        self.assertTrue((self.root / 'VALIDATE_R5C8_WINDOWS.bat').is_file())


if __name__ == '__main__':
    unittest.main()
