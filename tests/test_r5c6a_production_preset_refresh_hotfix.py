from pathlib import Path
import unittest


class ProductionPresetRefreshHotfixTests(unittest.TestCase):
    def test_refresh_does_not_pass_integer_flags_to_qt_finditems(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / 'app' / 'production_presets_workspace.py').read_text(encoding='utf-8')
        self.assertNotIn('findItems(current, 0)', text)
        self.assertIn('self.preset_list.setCurrentRow(names.index(current))', text)


if __name__ == '__main__':
    unittest.main()
