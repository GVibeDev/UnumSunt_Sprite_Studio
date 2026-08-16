from pathlib import Path
import tempfile
import unittest

from app.branding import (
    ICON_ICO_NAME,
    ICON_PNG_NAME,
    SPLASH_NAME,
    INSTALLER_WIZARD_NAME,
    INSTALLER_WIZARD_SMALL_NAME,
    resolve_branding_asset,
    splash_metadata_lines,
)
from app.version import APP_AUTHOR, APP_BUILD_LABEL, APP_LICENSE, APP_VERSION, APP_WINDOWS_APP_ID


class BrandingIntegrationTests(unittest.TestCase):
    def test_resolve_branding_asset_finds_assets_under_branding_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            branding = root / 'assets' / 'branding'
            branding.mkdir(parents=True)
            target = branding / ICON_PNG_NAME
            target.write_bytes(b'test')
            resolved = resolve_branding_asset(ICON_PNG_NAME, roots=[root])
            self.assertEqual(resolved, target)

    def test_splash_metadata_lines_include_required_fields(self):
        lines = splash_metadata_lines()
        self.assertGreaterEqual(len(lines), 5)
        self.assertIn(APP_VERSION, lines[0])
        self.assertIn(APP_BUILD_LABEL, lines[1])
        self.assertIn(APP_AUTHOR, lines[2])
        self.assertTrue(lines[3].startswith('Dependencies: '))
        self.assertIn(APP_LICENSE, lines[4])

    def test_spec_declares_branding_assets_and_icon(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / 'UnumSuntSpriteStudio.spec').read_text(encoding='utf-8')
        self.assertIn("branding_datas = [('assets/branding', 'assets/branding')]", spec)
        self.assertIn("icon='assets/branding/app_icon.ico'", spec)

    def test_installer_uses_branded_setup_assets(self):
        root = Path(__file__).resolve().parents[1]
        iss = (root / 'installer' / 'UnumSuntSpriteStudio_R5c7.iss').read_text(encoding='utf-8')
        self.assertIn('SetupIconFile=..\\assets\\branding\\app_icon.ico', iss)
        self.assertIn(f'WizardImageFile=..\\assets\\branding\\{INSTALLER_WIZARD_NAME}', iss)
        self.assertIn(f'WizardSmallImageFile=..\\assets\\branding\\{INSTALLER_WIZARD_SMALL_NAME}', iss)

    def test_windows_shell_app_id_is_declared(self):
        self.assertEqual(APP_WINDOWS_APP_ID, 'GVibeDev.UnumSuntSpriteStudio')
        main_text = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')
        self.assertIn('SetCurrentProcessExplicitAppUserModelID', main_text)

    def test_project_contains_required_branding_assets(self):
        root = Path(__file__).resolve().parents[1]
        branding = root / 'assets' / 'branding'
        self.assertTrue((branding / ICON_PNG_NAME).exists())
        self.assertTrue((branding / ICON_ICO_NAME).exists())
        self.assertTrue((branding / SPLASH_NAME).exists())
        self.assertTrue((branding / INSTALLER_WIZARD_NAME).exists())
        self.assertTrue((branding / INSTALLER_WIZARD_SMALL_NAME).exists())


if __name__ == '__main__':
    unittest.main()
