from pathlib import Path
import unittest


class R5c3bHuggingFaceDependencyContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.source = (self.root / 'app' / 'runtime_installer.py').read_text(encoding='utf-8')

    def test_installer_does_not_blindly_upgrade_huggingface_hub(self):
        self.assertNotIn('"--upgrade", "huggingface_hub"', self.source)

    def test_installer_reasserts_transformers_compatible_hub_range(self):
        self.assertIn('huggingface_hub[hf_xet]>=0.34.0,<1.0', self.source)

    def test_health_check_imports_transformers_and_huggingface_hub(self):
        self.assertIn('import transformers,huggingface_hub', self.source)
        self.assertIn('huggingface.compat', self.source)

    def test_health_check_runs_pip_check_as_diagnostic(self):
        self.assertIn('"pip", "check"', self.source)
        self.assertIn('python.pip_check', self.source)


if __name__ == '__main__':
    unittest.main()
