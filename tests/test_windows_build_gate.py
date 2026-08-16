from pathlib import Path
import unittest


class WindowsBuildGateTests(unittest.TestCase):
    def test_windowed_self_check_waits_for_process_and_reads_exit_code(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "build_windows_standalone.ps1").read_text(encoding="utf-8")
        self.assertIn("Start-Process -FilePath $exe", script)
        self.assertIn("-Wait -PassThru", script)
        self.assertIn("$selfCheckProcess.ExitCode", script)
        self.assertIn("Remove-Item -Force $selfCheck", script)


if __name__ == "__main__":
    unittest.main()
