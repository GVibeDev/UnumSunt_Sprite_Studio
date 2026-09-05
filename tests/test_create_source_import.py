from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.create_source_import import classify_create_source_path, import_dropped_create_source


class CreateSourceImportTests(unittest.TestCase):
    def test_classifies_supported_sources(self) -> None:
        self.assertEqual(classify_create_source_path('clip.mp4'), 'video')
        self.assertEqual(classify_create_source_path('sheet.PNG'), 'spritesheet')
        self.assertEqual(classify_create_source_path('sequence.json'), 'sequence_manifest')
        self.assertIsNone(classify_create_source_path('notes.txt'))

    def test_video_drop_reuses_video_callback_and_returns_to_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'clip.mp4'
            source.write_bytes(b'x')
            calls = []
            ok = import_dropped_create_source(
                [str(source)],
                open_video=lambda path: calls.append(('video', Path(path).name)) or True,
                open_spritesheet=lambda path: False,
                open_sequence_manifest=lambda path: False,
                navigate=lambda route: calls.append(('route', route)),
                show_canvas=lambda: calls.append(('canvas', True)),
                status=lambda text: calls.append(('status', text)),
            )
            self.assertTrue(ok)
            self.assertEqual(calls[0], ('video', 'clip.mp4'))
            self.assertIn(('route', 'extraction'), calls)
            self.assertIn(('canvas', True), calls)

    def test_spritesheet_drop_reuses_sheet_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'sheet.webp'
            source.write_bytes(b'x')
            calls = []
            ok = import_dropped_create_source(
                [str(source)],
                open_video=lambda path: False,
                open_spritesheet=lambda path: calls.append(('sheet', Path(path).name)) or True,
                open_sequence_manifest=lambda path: False,
                navigate=lambda route: calls.append(('route', route)),
                show_canvas=lambda: calls.append(('canvas', True)),
                status=lambda text: None,
            )
            self.assertTrue(ok)
            self.assertIn(('sheet', 'sheet.webp'), calls)
            self.assertIn(('route', 'spritesheet'), calls)

    def test_unsupported_drop_does_not_call_importers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'notes.txt'
            source.write_text('x', encoding='utf-8')
            calls = []
            ok = import_dropped_create_source(
                [str(source)],
                open_video=lambda path: calls.append(path) or True,
                open_spritesheet=lambda path: calls.append(path) or True,
                open_sequence_manifest=lambda path: calls.append(path) or True,
                navigate=lambda route: calls.append(route),
                show_canvas=lambda: calls.append('canvas'),
                status=lambda text: None,
            )
            self.assertFalse(ok)
            self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
