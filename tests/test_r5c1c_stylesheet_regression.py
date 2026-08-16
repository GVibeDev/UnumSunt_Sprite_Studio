from pathlib import Path
import unittest


class R5c1cStylesheetRegressionTests(unittest.TestCase):
    def test_export_background_swatch_fstring_uses_escaped_qss_braces(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'app' / 'export_studio.py').read_text(encoding='utf-8')
        self.assertIn("QLabel {{ color: #f4f6f8; background: rgb({r}, {g}, {b}); border: 1px solid #777; }}", source)
        self.assertNotIn("QLabel { color: #f4f6f8;{ background:", source)

    def test_no_known_malformed_dynamic_stylesheet_pattern_in_app(self):
        root = Path(__file__).resolve().parents[1] / 'app'
        offenders = []
        for path in root.rglob('*.py'):
            text = path.read_text(encoding='utf-8')
            if "setStyleSheet(f" in text and "{ color: #f4f6f8;{" in text:
                offenders.append(str(path.relative_to(root)))
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
