from pathlib import Path
import unittest


class SourceRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.script = (cls.root / 'run_windows.ps1').read_text(encoding='utf-8')
        cls.batch = (cls.root / 'run_windows.bat').read_text(encoding='utf-8')

    def test_source_runner_accepts_python_313_and_314_x64(self):
        self.assertIn("@('3.13','3.14') -contains $parts[0]", self.script)
        self.assertIn("$parts[1] -eq '64'", self.script)

    def test_source_runner_does_not_force_python_313(self):
        self.assertNotIn('py -3.13 -m venv', self.batch)
        self.assertIn('run_windows.ps1', self.batch)

    def test_source_runner_recreates_incompatible_venv(self):
        self.assertIn(".venv uses an unsupported or corrupted Python runtime", self.script)
        self.assertIn('Remove-Item -Recurse -Force $venv', self.script)

    def test_source_runner_uses_resolved_venv_python_for_pip_and_main(self):
        self.assertIn('& $venvPython -m pip install -r requirements.txt', self.script)
        self.assertIn('& $venvPython main.py', self.script)


if __name__ == '__main__':
    unittest.main()
