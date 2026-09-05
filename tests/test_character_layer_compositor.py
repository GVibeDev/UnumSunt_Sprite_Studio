from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from app.character_layer_compositor import (
    CharacterLayerCompositeError,
    compose_character_layers,
)


class CharacterLayerCompositorTests(unittest.TestCase):
    def _assignment(self, root: Path, frames: list[np.ndarray], *, mode: str = 'single') -> dict:
        layer_dir = root / 'layer'
        layer_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for index, frame in enumerate(frames):
            path = layer_dir / f'frame_{index:03d}.png'
            Image.fromarray(frame, mode='RGBA').save(path)
            files.append(str(path.resolve()))
        h, w = frames[0].shape[:2]
        manifest = {
            'mode': mode,
            'frame_count': len(frames),
            'width': w,
            'height': h,
            'files': files,
        }
        manifest_path = layer_dir / 'layer_manifest.json'
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        return {
            'manifest_path': str(manifest_path.resolve()),
            'mode': mode,
            'frame_count': len(frames),
            'width': w,
            'height': h,
            'has_alpha': True,
            'offset_x': 1,
            'offset_y': 1,
            'visible': True,
        }

    def test_single_equipment_layer_composites_over_every_base_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = np.zeros((4, 4, 4), dtype=np.uint8)
            base[:, :, 0] = 255
            base[:, :, 3] = 255
            overlay = np.zeros((2, 2, 4), dtype=np.uint8)
            overlay[:, :, 1] = 255
            overlay[:, :, 3] = 255
            assignment = self._assignment(root, [overlay])
            character_set = {
                'layers': [{
                    'id': 'equipment', 'name': 'Sword', 'kind': 'equipment',
                    'enabled': True, 'export_enabled': True, 'opacity': 1.0, 'order': 0,
                }]
            }
            stack = {'assignments': {'equipment': assignment}}
            result, report = compose_character_layers(
                [base, base], character_set=character_set, direction_stack=stack, for_export=True,
            )
            self.assertEqual(len(result), 2)
            np.testing.assert_array_equal(result[0][1, 1], np.array([0, 255, 0, 255], dtype=np.uint8))
            np.testing.assert_array_equal(result[0][0, 0], np.array([255, 0, 0, 255], dtype=np.uint8))
            self.assertEqual(report['applied_layer_count'], 1)

    def test_preview_can_show_layer_that_export_excludes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = np.zeros((3, 3, 4), dtype=np.uint8)
            base[:, :, 3] = 255
            overlay = np.zeros((1, 1, 4), dtype=np.uint8)
            overlay[0, 0] = [255, 255, 255, 255]
            assignment = self._assignment(root, [overlay])
            character_set = {
                'layers': [{
                    'id': 'fx', 'name': 'FX', 'kind': 'effect',
                    'enabled': True, 'export_enabled': False, 'opacity': 1.0, 'order': 0,
                }]
            }
            stack = {'assignments': {'fx': assignment}}
            preview, preview_report = compose_character_layers(
                [base], character_set=character_set, direction_stack=stack, for_export=False,
            )
            exported, export_report = compose_character_layers(
                [base], character_set=character_set, direction_stack=stack, for_export=True,
            )
            self.assertEqual(preview_report['applied_layer_count'], 1)
            self.assertEqual(export_report['applied_layer_count'], 0)
            self.assertFalse(np.array_equal(preview[0], base))
            np.testing.assert_array_equal(exported[0], base)

    def test_sequence_mismatch_is_rejected_instead_of_cycled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = np.zeros((4, 4, 4), dtype=np.uint8)
            layer_frame = np.zeros((2, 2, 4), dtype=np.uint8)
            layer_frame[:, :, 3] = 255
            assignment = self._assignment(root, [layer_frame, layer_frame], mode='sequence')
            character_set = {
                'layers': [{
                    'id': 'outfit', 'name': 'Outfit', 'kind': 'outfit',
                    'enabled': True, 'export_enabled': True, 'opacity': 1.0, 'order': 0,
                }]
            }
            stack = {'assignments': {'outfit': assignment}}
            with self.assertRaisesRegex(CharacterLayerCompositeError, '2 frames.*3'):
                compose_character_layers(
                    [base, base, base], character_set=character_set, direction_stack=stack, for_export=True,
                )

    def test_missing_assigned_manifest_is_blocking(self) -> None:
        base = np.zeros((4, 4, 4), dtype=np.uint8)
        character_set = {
            'layers': [{
                'id': 'equipment', 'name': 'Sword', 'kind': 'equipment',
                'enabled': True, 'export_enabled': True, 'opacity': 1.0, 'order': 0,
            }]
        }
        stack = {'assignments': {'equipment': {
            'manifest_path': '/definitely/missing/layer_manifest.json',
            'mode': 'single', 'frame_count': 1, 'width': 1, 'height': 1,
            'visible': True,
        }}}
        with self.assertRaisesRegex(CharacterLayerCompositeError, 'manifest is missing'):
            compose_character_layers([base], character_set=character_set, direction_stack=stack, for_export=True)


if __name__ == '__main__':
    unittest.main()
