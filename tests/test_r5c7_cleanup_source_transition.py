from pathlib import Path
import unittest


class R5c7CleanupSourceTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.cleanup = (root / 'app' / 'cleanup_studio.py').read_text(encoding='utf-8')
        cls.main = (root / 'app' / 'main_window.py').read_text(encoding='utf-8')

    def test_cleanup_uses_qsignalblocker_for_list_mutation(self):
        self.assertIn('from PySide6.QtCore import Qt, Signal, QSignalBlocker', self.cleanup)
        self.assertIn('with QSignalBlocker(self.frame_list):', self.cleanup)

    def test_cleanup_has_explicit_source_transition_quiesce(self):
        self.assertIn('def prepare_source_change(self) -> None:', self.cleanup)
        self.assertIn('self._source_transition = True', self.cleanup)
        self.assertIn("self.info_label.setText('Cambio sorgente in corso…')", self.cleanup)

    def test_current_item_handler_does_not_repopulate_its_own_list(self):
        start = self.cleanup.index('def _on_frame_item_changed')
        end = self.cleanup.index('def _select_relative', start)
        handler = self.cleanup[start:end]
        self.assertNotIn('self.set_selected_frames(', handler)
        self.assertNotIn('frame_list.clear()', handler)
        self.assertIn('if self._source_transition or current is None:', handler)

    def test_video_open_quiesces_cleanup_before_source_replace(self):
        self.assertIn(
            'self.cleanup_studio.prepare_source_change()\n        try:\n            metadata = self.video.open(path)',
            self.main,
        )
        self.assertIn(
            'self.cleanup_studio.prepare_source_change()\n        try:\n            metadata = self.video.open_sequence_manifest(manifest_path)',
            self.main,
        )

    def test_video_close_quiesces_cleanup_before_close(self):
        self.assertIn(
            'self.cleanup_studio.prepare_source_change()\n        self.video.close()',
            self.main,
        )

    def test_group_change_quiesces_cleanup_after_snapshot(self):
        marker = 'def _on_active_group_will_change'
        start = self.main.index(marker)
        end = self.main.index('def _clear_loaded_video_context', start)
        body = self.main[start:end]
        self.assertIn('self._save_active_group_snapshot()', body)
        self.assertIn('self.cleanup_studio.prepare_source_change()', body)


if __name__ == '__main__':
    unittest.main()
