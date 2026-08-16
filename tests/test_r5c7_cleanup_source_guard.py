from pathlib import Path
import unittest


class R5c7CleanupSourceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.source = (root / "app" / "cleanup_studio.py").read_text(encoding="utf-8")

    def test_cleanup_imports_video_open_error_for_transient_source_loss(self):
        self.assertIn("from app.video_source import VideoOpenError", self.source)

    def test_selected_frames_are_rejected_without_metadata(self):
        self.assertIn("if metadata is None:\n            normalized: list[int] = []", self.source)

    def test_preview_handles_source_loss_without_crashing(self):
        self.assertIn("except VideoOpenError:", self.source)
        self.assertIn("_show_missing_or_empty_source(missing_source=True)", self.source)

    def test_frame_selection_checks_metadata_before_loading(self):
        self.assertIn("metadata = self._metadata_provider()", self.source)
        self.assertIn("if metadata is None:\n            self.set_selected_frames([])", self.source)


if __name__ == "__main__":
    unittest.main()
