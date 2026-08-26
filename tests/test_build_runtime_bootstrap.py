from pathlib import Path
import unittest


class BuildRuntimeBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.script = (cls.root / 'build_windows_standalone.ps1').read_text(encoding='utf-8')

    def test_build_runtime_is_locked_to_python_313_x64(self):
        self.assertIn("$BuildPythonTag = '3.13'", self.script)
        self.assertIn("$parts[0] -eq '3.13'", self.script)
        self.assertIn("$parts[1] -eq '64'", self.script)

    def test_existing_wrong_build_venv_is_recreated(self):
        self.assertIn(".build-venv uses an incompatible Python version", self.script)
        self.assertIn('Remove-Item -Recurse -Force $venv', self.script)

    def test_bootstrap_prefers_python_install_manager(self):
        self.assertIn('Get-PythonManagerPath', self.script)
        self.assertIn('& $manager install $BuildPythonTag', self.script)
        self.assertIn('pymanager', self.script)

    def test_python_manager_can_be_bootstrapped_with_winget(self):
        self.assertIn('winget', self.script)
        self.assertIn('9NQ7512CXL7T', self.script)
        self.assertIn('--accept-package-agreements', self.script)
        self.assertIn('--disable-interactivity', self.script)

    def test_bootstrap_has_interactive_and_noninteractive_modes(self):
        self.assertIn('[switch]$InstallPython313', self.script)
        self.assertIn('[switch]$NoPythonInstallPrompt', self.script)
        self.assertIn("Read-Host 'Install Python 3.13 x64 automatically for this build? [Y/N]'", self.script)


    def test_powershell_variable_before_colon_is_delimited(self):
        self.assertIn('${BuildPythonLabel} contract: $basePython', self.script)
        self.assertNotIn('$BuildPythonLabel contract: $basePython', self.script)

    def test_manager_install_uses_standard_313_tag_and_explicit_x64_validation(self):
        self.assertIn('& $manager install $BuildPythonTag', self.script)
        self.assertIn("$parts[1] -eq '64'", self.script)
        self.assertIn('& $manager list --one --format=exe $BuildPythonTag', self.script)

    def test_build_never_uses_bare_python_command_for_runtime_selection(self):
        # Build commands after bootstrap must use the resolved .build-venv interpreter.
        self.assertIn('& $python -m pip install -r requirements-build.txt', self.script)
        self.assertIn('& $python -m PyInstaller', self.script)


if __name__ == '__main__':
    unittest.main()
