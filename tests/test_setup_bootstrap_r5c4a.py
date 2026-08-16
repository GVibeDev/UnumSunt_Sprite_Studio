from pathlib import Path
import unittest


class SetupBootstrapR5c4aTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.script = (cls.root / "build_setup_windows.ps1").read_text(encoding="utf-8")

    def test_discovers_per_user_inno_setup(self):
        self.assertIn("$env:LOCALAPPDATA", self.script)
        self.assertIn("Programs\\Inno Setup 7\\ISCC.exe", self.script)
        self.assertIn("Programs\\Inno Setup 6\\ISCC.exe", self.script)

    def test_discovers_inno_setup_from_registry(self):
        self.assertIn("CurrentVersion\\Uninstall\\*", self.script)
        self.assertIn("InstallLocation", self.script)
        self.assertIn("App Paths\\ISCC.exe", self.script)

    def test_uses_current_and_legacy_winget_ids(self):
        self.assertIn("JRSoftware.InnoSetup.7", self.script)
        self.assertIn("JRSoftware.InnoSetup", self.script)

    def test_winget_exit_is_not_authoritative_when_iscc_exists(self):
        marker = "$detected = Find-Iscc"
        self.assertIn(marker, self.script)
        self.assertLess(self.script.index(marker), self.script.index("if ($wingetExit -ne 0)"))

    def test_r5c4a_installer_contract(self):
        self.assertIn("UnumSuntSpriteStudio_R5c4a.iss", self.script)
        self.assertIn("UnumSunt_Sprite_Studio_R5c4a_Setup_x64.exe", self.script)
        self.assertTrue((self.root / "installer" / "UnumSuntSpriteStudio_R5c4a.iss").is_file())


if __name__ == "__main__":
    unittest.main()
