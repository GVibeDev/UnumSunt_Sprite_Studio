from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class P2GAValidationHotfixContractTests(unittest.TestCase):
    def test_cleanup_alpha_checkbox_does_not_pass_qt_bool_into_keyword_only_refresh(self) -> None:
        source = (ROOT / 'app' / 'cleanup_studio.py').read_text(encoding='utf-8')
        self.assertIn("self.alpha_only_checkbox.toggled.connect(lambda _checked: self._refresh_current_preview())", source)
        self.assertNotIn('self.alpha_only_checkbox.toggled.connect(self._refresh_current_preview)', source)

    def test_alignment_onion_is_bridged_to_shared_create_canvas(self) -> None:
        alignment = (ROOT / 'app' / 'alignment_studio.py').read_text(encoding='utf-8')
        main = (ROOT / 'app' / 'main_window.py').read_text(encoding='utf-8')
        shell = (ROOT / 'app' / 'workstation_shell.py').read_text(encoding='utf-8')
        self.assertIn('onion_view_changed = Signal(bool, float)', alignment)
        self.assertIn('self.alignment_studio.onion_view_changed.connect(sync_alignment_onion)', main)
        self.assertIn("self.workstation_shell.set_create_onion_mode('previous' if enabled else 'off')", main)
        self.assertIn('def set_create_canvas_onion_opacity', shell)

    def test_character_set_has_real_preview_and_composite_export_route(self) -> None:
        workspace = (ROOT / 'app' / 'character_set_workspace.py').read_text(encoding='utf-8')
        export = (ROOT / 'app' / 'export_studio.py').read_text(encoding='utf-8')
        main = (ROOT / 'app' / 'main_window.py').read_text(encoding='utf-8')
        controller = (ROOT / 'app' / 'character_set_composite_controller.py').read_text(encoding='utf-8')
        self.assertIn("preview_button = QPushButton('Preview Composite')", workspace)
        self.assertIn("QCheckBox('Include in Character Set composite export')", workspace)
        self.assertIn("'Character Set composite (R2 + visible export layers)', 'character_set'", export)
        self.assertIn('character_set_frames_provider=self.character_set_composite.build_export_payload', main)
        self.assertIn('compose_character_layers(', controller)


if __name__ == '__main__':
    unittest.main()
