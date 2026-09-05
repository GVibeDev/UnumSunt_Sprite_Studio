from __future__ import annotations

import importlib.util
import os
import unittest

PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None

if PYSIDE6_AVAILABLE:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication

    from app.create_frame_context import CreateFrameContext
    from app.create_frame_strip import CreateFrameStrip


@unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is not installed in this test interpreter.')
class CreateFrameStripQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_context_updates_virtualized_model_and_status(self) -> None:
        strip = CreateFrameStrip()
        context = CreateFrameContext(
            frame_count=120,
            current_frame_index=7,
            selected_frames=(2, 7, 12),
            fps=24.0,
            source_kind='video',
            source_label='walk.mp4',
        )
        strip.update_context(context)
        self.assertEqual(strip.model.rowCount(), 120)
        self.assertEqual(strip.frame_spin.value(), 7)
        self.assertIn('Selected: 3', strip.frame_context_label.text())
        self.assertIn('walk.mp4', strip.source_label.text())
        self.assertIn('▶●', strip.model.data(strip.model.index(7, 0)))

    def test_select_and_deselect_current_emit_complete_selection(self) -> None:
        strip = CreateFrameStrip()
        strip.update_context(CreateFrameContext(frame_count=10, current_frame_index=4, selected_frames=(1, 2)))
        observed: list[tuple[int, ...]] = []
        strip.selection_requested.connect(lambda values: observed.append(tuple(values)))
        strip.select_current_button.click()
        self.assertEqual(observed[-1], (1, 2, 4))
        strip.update_context(CreateFrameContext(frame_count=10, current_frame_index=4, selected_frames=(1, 2, 4)))
        strip.deselect_current_button.click()
        self.assertEqual(observed[-1], (1, 2))

    def test_onion_mode_is_explicit(self) -> None:
        strip = CreateFrameStrip()
        observed: list[str] = []
        strip.onion_mode_changed.connect(observed.append)
        strip.onion_combo.setCurrentIndex(strip.onion_combo.findData('previous'))
        self.assertEqual(strip.onion_mode, 'previous')
        self.assertEqual(observed[-1], 'previous')


if __name__ == '__main__':
    unittest.main()
