from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from PIL import Image

from app.export_service import export_selected_frames, export_rgba_bundle, apply_background_to_rgba, scale_rgba_nearest
from app.models import (
    ChromaKeySettings,
    ExportSettings,
    VideoMetadata,
)


class ExportServiceTests(unittest.TestCase):
    def test_export_png_and_manifest(self) -> None:
        frame = np.zeros((80, 100, 3), dtype=np.uint8)
        frame[:] = (0, 255, 0)
        frame[20:60, 30:70] = (180, 70, 30)

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            metadata = VideoMetadata(
                path=temp_path / "source.mp4",
                width=100,
                height=80,
                fps=25.0,
                frame_count=10,
            )
            manifest = export_selected_frames(
                frame_indices=[3],
                frame_loader=lambda _: frame.copy(),
                video_metadata=metadata,
                chroma_settings=ChromaKeySettings(
                    background_rgb=(0, 255, 0),
                    tolerance=15,
                    softness=0,
                    cleanup_radius=0,
                    edge_decontamination=0,
                ),
                export_settings=ExportSettings(
                    output_format="png",
                    crop_to_subject=True,
                    padding=2,
                ),
                output_directory=temp_path / "output",
            )

            output_file = temp_path / "output" / "frame-000003.png"
            manifest_file = temp_path / "output" / "export-manifest.json"
            self.assertTrue(output_file.exists())
            self.assertTrue(manifest_file.exists())
            self.assertEqual(len(manifest["frames"]), 1)

            with Image.open(output_file) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (44, 44))

    def test_manifest_contains_structural_mask_settings(self) -> None:
        frame = np.zeros((40, 40, 3), dtype=np.uint8)
        frame[:] = (0, 255, 0)
        frame[10:30, 10:30] = (200, 40, 30)
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            metadata = VideoMetadata(path=temp_path / 'source.mp4', width=40, height=40, fps=12.0, frame_count=1)
            manifest = export_selected_frames(
                frame_indices=[0],
                frame_loader=lambda _: frame.copy(),
                video_metadata=metadata,
                chroma_settings=ChromaKeySettings(
                    background_rgb=(0, 255, 0), tolerance=2, softness=0, cleanup_radius=0, edge_decontamination=0,
                    outer_border_mask_px=4, subject_edge_mask_expand_px=2,
                ),
                export_settings=ExportSettings(output_format='png', crop_to_subject=False),
                output_directory=temp_path / 'output',
            )
            self.assertEqual(manifest['chroma_key']['outer_border_mask_px'], 4)
            self.assertEqual(manifest['chroma_key']['subject_edge_mask_expand_px'], 2)

    def test_export_rgba_bundle_grid_solid_background(self) -> None:
        frame_a = np.zeros((4, 4, 4), dtype=np.uint8)
        frame_a[1:3, 1:3] = (255, 0, 0, 255)
        frame_b = np.zeros((4, 4, 4), dtype=np.uint8)
        frame_b[0:2, 0:2] = (0, 0, 255, 255)

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = export_rgba_bundle(
                rgba_frames=[frame_a, frame_b],
                output_directory=temp_path / 'bundle',
                base_name='walk-se',
                output_format='png',
                include_frames=True,
                include_sheet=True,
                sheet_layout='grid',
                sheet_columns=1,
                sheet_padding=2,
                scale_factor=2,
                background_mode='solid',
                background_rgb=(10, 20, 30),
                source_kind='aligned',
            )
            self.assertEqual(manifest['frame_count'], 2)
            self.assertEqual(manifest['frame_size'], [8, 8])
            self.assertEqual(manifest['sheet']['rows'], 2)
            self.assertTrue((temp_path / 'bundle' / 'walk-se-spritesheet.png').exists())

            with Image.open(temp_path / 'bundle' / 'walk-se-frame-000.png') as image:
                self.assertEqual(image.size, (8, 8))
                self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 255))

    def test_background_and_scaling_helpers(self) -> None:
        rgba = np.zeros((2, 2, 4), dtype=np.uint8)
        rgba[0, 0] = (100, 50, 25, 128)
        flattened = apply_background_to_rgba(rgba, mode='solid', background_rgb=(0, 0, 0))
        self.assertEqual(flattened.shape, rgba.shape)
        self.assertEqual(int(flattened[0, 0, 3]), 255)
        scaled = scale_rgba_nearest(flattened, factor=3)
        self.assertEqual(scaled.shape[:2], (6, 6))


if __name__ == "__main__":
    unittest.main()
