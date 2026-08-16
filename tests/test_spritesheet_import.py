from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.spritesheet_import import (
    AtlasRegion,
    GridSliceSettings,
    auto_detect_regular_grid,
    create_reference_sheet,
    detect_atlas_regions,
    extract_atlas_frames,
    load_sequence_manifest,
    normalize_frames_to_canvas,
    save_rgba_png,
    save_sequence_manifest,
    slice_regular_sheet,
)
from app.video_source import VideoOpenError, VideoSource


class SpriteSheetImportTests(unittest.TestCase):
    def _frame(self, width: int, height: int, rgba=(255, 0, 0, 255)) -> np.ndarray:
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        arr[:] = rgba
        return arr

    def test_regular_grid_row_major(self) -> None:
        sheet = np.zeros((6, 10, 4), dtype=np.uint8)
        sheet[1:3, 1:4] = (255, 0, 0, 255)
        sheet[1:3, 6:9] = (0, 255, 0, 255)
        sheet[4:6, 1:4] = (0, 0, 255, 255)
        sheet[4:6, 6:9] = (255, 255, 0, 255)
        settings = GridSliceSettings(
            frame_width=3, frame_height=2, rows=2, columns=2,
            horizontal_padding=2, vertical_padding=1, outer_margin=1,
        )
        frames, rects = slice_regular_sheet(sheet, settings)
        self.assertEqual(rects, [(1, 1, 3, 2), (6, 1, 3, 2), (1, 4, 3, 2), (6, 4, 3, 2)])
        self.assertEqual(tuple(frames[0][0, 0]), (255, 0, 0, 255))
        self.assertEqual(tuple(frames[3][0, 0]), (255, 255, 0, 255))

    def test_regular_grid_column_major(self) -> None:
        sheet = np.zeros((4, 4, 4), dtype=np.uint8)
        sheet[:2, :2] = (1, 0, 0, 255)
        sheet[:2, 2:] = (2, 0, 0, 255)
        sheet[2:, :2] = (3, 0, 0, 255)
        sheet[2:, 2:] = (4, 0, 0, 255)
        settings = GridSliceSettings(2, 2, 2, 2, reading_order='column_major')
        frames, _ = slice_regular_sheet(sheet, settings)
        self.assertEqual([int(frame[0, 0, 0]) for frame in frames], [1, 3, 2, 4])

    def test_grid_rejects_out_of_bounds(self) -> None:
        sheet = np.zeros((8, 8, 4), dtype=np.uint8)
        settings = GridSliceSettings(5, 5, 2, 2)
        with self.assertRaises(ValueError):
            slice_regular_sheet(sheet, settings)

    def test_auto_detect_transparent_regular_grid(self) -> None:
        sheet = np.zeros((13, 15, 4), dtype=np.uint8)
        # margin 1, cells 5x4, gaps 3x3
        sheet[1:5, 1:6] = (255, 0, 0, 255)
        sheet[1:5, 9:14] = (0, 255, 0, 255)
        sheet[8:12, 1:6] = (0, 0, 255, 255)
        sheet[8:12, 9:14] = (255, 255, 0, 255)
        result = auto_detect_regular_grid(sheet)
        self.assertIn(result.confidence, {'high', 'medium'})
        self.assertEqual(result.settings.frame_width, 5)
        self.assertEqual(result.settings.frame_height, 4)
        self.assertEqual(result.settings.columns, 2)
        self.assertEqual(result.settings.rows, 2)
        self.assertEqual(result.settings.horizontal_padding, 3)
        self.assertEqual(result.settings.vertical_padding, 3)

    def test_auto_detect_fallback_single_frame(self) -> None:
        rng = np.random.default_rng(1)
        sheet = np.concatenate([
            rng.integers(0, 255, size=(7, 9, 3), dtype=np.uint8),
            np.full((7, 9, 1), 255, dtype=np.uint8),
        ], axis=2)
        result = auto_detect_regular_grid(sheet)
        self.assertIn(result.confidence, {'low', 'medium'})
        self.assertGreaterEqual(result.settings.rows, 1)
        self.assertGreaterEqual(result.settings.columns, 1)

    def test_atlas_components_detected_in_reading_order(self) -> None:
        sheet = np.zeros((20, 30, 4), dtype=np.uint8)
        sheet[2:7, 3:8] = (255, 0, 0, 255)
        sheet[10:18, 20:28] = (0, 255, 0, 255)
        regions = detect_atlas_regions(sheet, min_area=4)
        self.assertEqual(len(regions), 2)
        self.assertEqual((regions[0].x, regions[0].y, regions[0].width, regions[0].height), (3, 2, 5, 5))
        self.assertEqual((regions[1].x, regions[1].y), (20, 10))

    def test_atlas_opaque_returns_no_regions(self) -> None:
        sheet = np.full((10, 10, 4), 255, dtype=np.uint8)
        self.assertEqual(detect_atlas_regions(sheet), [])

    def test_atlas_extract_and_normalize_bottom_center(self) -> None:
        sheet = np.zeros((16, 20, 4), dtype=np.uint8)
        sheet[1:5, 1:4] = (255, 0, 0, 255)
        sheet[7:15, 10:17] = (0, 255, 0, 255)
        regions = [AtlasRegion(1, 1, 3, 4, 12), AtlasRegion(10, 7, 7, 8, 56)]
        raw = extract_atlas_frames(sheet, regions)
        frames, canvas, offsets = normalize_frames_to_canvas(raw, alignment='bottom_center')
        self.assertEqual(canvas, (7, 8))
        self.assertEqual(offsets[0], (2, 4))
        self.assertEqual(offsets[1], (0, 0))
        self.assertEqual(frames[0].shape, (8, 7, 4))
        self.assertTrue(np.all(frames[0][4:8, 2:5, 3] == 255))

    def test_reference_sheet_uses_selected_indices(self) -> None:
        frames = [self._frame(4, 5, (i, 0, 0, 255)) for i in range(6)]
        sheet, manifest = create_reference_sheet(frames, [0, 2, 5], columns=2, padding=1)
        self.assertEqual(manifest['selected_indices'], [0, 2, 5])
        self.assertEqual(manifest['columns'], 2)
        self.assertEqual(manifest['rows'], 2)
        self.assertEqual(len(manifest['placements']), 3)
        self.assertEqual(sheet.shape[2], 4)

    def test_reference_sheet_requires_selection(self) -> None:
        with self.assertRaises(ValueError):
            create_reference_sheet([self._frame(2, 2)], [], columns=1)

    def test_sequence_manifest_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'sheet.png'
            save_rgba_png(source, self._frame(2, 2))
            frames_dir = root / 'frames'
            p0 = frames_dir / 'frame_0000.png'
            p1 = frames_dir / 'frame_0001.png'
            save_rgba_png(p0, self._frame(2, 2, (1, 2, 3, 255)))
            save_rgba_png(p1, self._frame(2, 2, (4, 5, 6, 100)))
            manifest_path = save_sequence_manifest(
                root / 'import_manifest.json',
                source_sheet=source,
                frame_paths=[p0, p1],
                fps=12,
                extraction={'mode': 'grid'},
                source_indices=[4, 8],
            )
            payload = load_sequence_manifest(manifest_path)
            self.assertEqual(payload['source_indices'], [4, 8])
            self.assertEqual(payload['fps'], 12.0)
            self.assertEqual([Path(p).name for p in payload['frame_paths']], ['frame_0000.png', 'frame_0001.png'])

    def test_video_source_sequence_preserves_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p0 = root / 'a.png'
            p1 = root / 'b.png'
            a = self._frame(4, 3, (20, 30, 40, 255))
            b = self._frame(4, 3, (50, 60, 70, 255))
            b[1, 1, 3] = 0
            save_rgba_png(p0, a)
            save_rgba_png(p1, b)
            source = VideoSource()
            metadata = source.open_frame_sequence([p0, p1], fps=8, source_path=root / 'sheet.png')
            self.assertEqual(source.source_kind, 'sequence')
            self.assertEqual(metadata.frame_count, 2)
            self.assertEqual(metadata.fps, 8.0)
            self.assertEqual(int(source.get_frame_rgba(1)[1, 1, 3]), 0)
            self.assertEqual(source.get_frame_rgb(0).shape, (3, 4, 3))

    def test_video_source_sequence_rejects_mixed_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p0 = root / 'a.png'
            p1 = root / 'b.png'
            save_rgba_png(p0, self._frame(4, 3))
            save_rgba_png(p1, self._frame(5, 3))
            with self.assertRaises(VideoOpenError):
                VideoSource().open_frame_sequence([p0, p1], fps=12)

    def test_video_source_opens_saved_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_sheet = root / 'sheet.png'
            save_rgba_png(source_sheet, self._frame(3, 3))
            p0 = root / 'frames' / 'f0.png'
            p1 = root / 'frames' / 'f1.png'
            save_rgba_png(p0, self._frame(3, 3))
            save_rgba_png(p1, self._frame(3, 3))
            manifest = save_sequence_manifest(
                root / 'sequence.json', source_sheet=source_sheet,
                frame_paths=[p0, p1], fps=9, extraction={'mode': 'grid'}
            )
            src = VideoSource()
            metadata = src.open_sequence_manifest(manifest)
            self.assertEqual(metadata.frame_count, 2)
            self.assertEqual(src.sequence_manifest_path, manifest.resolve())
            self.assertEqual(metadata.path, source_sheet.resolve())


if __name__ == '__main__':
    unittest.main()
