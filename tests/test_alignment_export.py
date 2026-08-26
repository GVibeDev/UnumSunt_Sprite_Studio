from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from PIL import Image

from app.alignment_engine import SubjectFrame
from app.alignment_export import export_aligned_animation
from app.models import (
    AlignmentSettings,
    ChromaKeySettings,
    FrameAlignmentState,
    VideoMetadata,
)


class AlignmentExportTests(unittest.TestCase):
    def _sample_subjects_and_states(self):
        rgba = np.zeros((20, 16, 4), dtype=np.uint8)
        rgba[2:20, 3:13, :3] = (120, 80, 50)
        rgba[2:20, 3:13, 3] = 255
        subjects = {
            index: SubjectFrame(
                frame_index=index,
                rgba=rgba.copy(),
                crop_box=(0, 0, 16, 20),
                auto_pivot_x=8,
                auto_pivot_y=20,
            )
            for index in (2, 5)
        }
        states = {
            index: FrameAlignmentState(
                frame_index=index,
                source_pivot_x=8,
                source_pivot_y=20,
            )
            for index in (2, 5)
        }
        return subjects, states

    def _metadata(self, temp_path: Path) -> VideoMetadata:
        return VideoMetadata(
            path=temp_path / 'source.mp4',
            width=720,
            height=720,
            fps=25.0,
            frame_count=100,
        )

    def test_export_frames_sheet_and_manifest(self) -> None:
        subjects, states = self._sample_subjects_and_states()

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = export_aligned_animation(
                frame_indices=[2, 5],
                subjects=subjects,
                states=states,
                video_metadata=self._metadata(temp_path),
                chroma_settings=ChromaKeySettings(),
                alignment_settings=AlignmentSettings(
                    canvas_width=96,
                    canvas_height=96,
                    canvas_pivot_x=48,
                    canvas_pivot_y=88,
                    shared_scale=1.0,
                    fps=10,
                ),
                output_directory=temp_path,
                animation_name='Walk',
                direction='South-East',
                output_format='png',
                sheet_layout='horizontal',
                sheet_padding=0,
            )

            self.assertEqual(manifest['schema'], 'unum-sunt-sprite-studio-animation-v4')
            self.assertEqual(len(manifest['frames']), 2)
            self.assertTrue((temp_path / 'walk-south-east-frame-000.png').exists())
            self.assertTrue((temp_path / 'walk-south-east-frame-001.png').exists())
            self.assertTrue((temp_path / 'walk-south-east-spritesheet.png').exists())
            self.assertTrue((temp_path / 'walk-south-east-manifest.json').exists())
            self.assertEqual(manifest['export_options']['mirror_mode'], 'none')

            with Image.open(temp_path / 'walk-south-east-spritesheet.png') as image:
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.size, (192, 96))


    def test_export_rectangular_canvas_and_geometry_manifest(self) -> None:
        subjects, states = self._sample_subjects_and_states()

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = export_aligned_animation(
                frame_indices=[2, 5],
                subjects=subjects,
                states=states,
                video_metadata=self._metadata(temp_path),
                chroma_settings=ChromaKeySettings(),
                alignment_settings=AlignmentSettings(
                    canvas_width=96,
                    canvas_height=128,
                    canvas_pivot_x=48,
                    canvas_pivot_y=120,
                    shared_scale=1.0,
                    fps=10,
                ),
                output_directory=temp_path,
                animation_name='Walk',
                direction='South-East',
                output_format='png',
                sheet_layout='grid',
                sheet_columns=1,
                sheet_padding=2,
            )

            self.assertEqual(manifest['canvas']['size'], [96, 128])
            self.assertEqual(manifest['canvas']['shape'], 'portrait')
            self.assertEqual(manifest['geometry_diagnostics']['size'], [96, 128])
            self.assertEqual(manifest['geometry_diagnostics']['clipped_frame_count'], 0)
            with Image.open(temp_path / 'walk-south-east-frame-000.png') as image:
                self.assertEqual(image.size, (96, 128))
            with Image.open(temp_path / 'walk-south-east-spritesheet.png') as image:
                self.assertEqual(image.size, (96, 258))

    def test_export_mirrored_opposite_direction(self) -> None:
        subjects, states = self._sample_subjects_and_states()

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest = export_aligned_animation(
                frame_indices=[2, 5],
                subjects=subjects,
                states=states,
                video_metadata=self._metadata(temp_path),
                chroma_settings=ChromaKeySettings(),
                alignment_settings=AlignmentSettings(
                    canvas_width=96,
                    canvas_height=96,
                    canvas_pivot_x=48,
                    canvas_pivot_y=88,
                    shared_scale=1.0,
                    fps=10,
                ),
                output_directory=temp_path,
                animation_name='Walk',
                direction='south-east',
                output_format='png',
                sheet_layout='horizontal',
                sheet_padding=0,
                mirror_mode='opposite-lateral',
            )

            self.assertTrue((temp_path / 'walk-south-west-frame-000.png').exists())
            self.assertTrue((temp_path / 'walk-south-west-frame-001.png').exists())
            self.assertTrue((temp_path / 'walk-south-west-spritesheet.png').exists())
            self.assertTrue((temp_path / 'walk-south-west-manifest.json').exists())
            self.assertIn('mirrored_export', manifest)
            self.assertEqual(manifest['mirrored_export']['direction'], 'south-west')
            self.assertEqual(manifest['mirrored_export']['mirrored_from_direction'], 'south-east')
            self.assertEqual(len(manifest['generated_exports']), 2)
            self.assertEqual(manifest['export_options']['mirror_mode'], 'opposite-lateral')

    def test_export_mirror_rejects_north(self) -> None:
        subjects, states = self._sample_subjects_and_states()

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with self.assertRaisesRegex(Exception, 'Horizontal mirroring'):
                export_aligned_animation(
                    frame_indices=[2, 5],
                    subjects=subjects,
                    states=states,
                    video_metadata=self._metadata(temp_path),
                    chroma_settings=ChromaKeySettings(),
                    alignment_settings=AlignmentSettings(),
                    output_directory=temp_path,
                    animation_name='Walk',
                    direction='north',
                    mirror_mode='opposite-lateral',
                )


if __name__ == '__main__':
    unittest.main()
