from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.production_presets import (
    ProductionPresetStore,
    build_production_preset,
    merge_preset_into_pipeline,
    sanitize_pipeline_state_for_preset,
    starter_presets,
)
from app.profile_store import ProfilesStore


class ProductionPresetTests(unittest.TestCase):
    def sample_pipeline(self) -> dict:
        return {
            'generation': {
                'local_config': {'python_executable': 'C:/private/python.exe'},
                'generation_profile': {
                    'reference_image': 'C:/subject.png',
                    'motion_video': 'C:/walk.mp4',
                    'positive_prompt': 'walk cycle',
                    'negative_prompt': 'camera motion',
                    'seed': 123,
                    'resolution_class': '480p',
                    'frames': 49,
                    'steps': 30,
                },
            },
            'chroma': {'background_rgb': [0, 255, 0], 'tolerance': 28},
            'selection': {
                'selected_frames': [1, 5, 9],
                'smart_selection': {
                    'start_frame': 0,
                    'end_frame': 48,
                    'sample_step': 1,
                    'profile': 'walk',
                    'desired_frames': 6,
                    'duplicate_sensitivity': 50,
                    'avoid_anomalies': True,
                    'r1_selection': [1, 5, 9],
                },
            },
            'cleanup': {'frame_indices': [1], 'override_file': 'cleanup/rgba_overrides.npz'},
            'alignment': {
                'profile': {'canvas_width': 96, 'canvas_height': 96, 'animation_name': 'walk'},
                'selected_indices': [1, 5, 9],
                'frame_states': {'1': {'frame_index': 1}},
            },
            'export': {'studio': {'source_mode': 'aligned', 'background_mode': 'transparent'}},
        }

    def test_sanitize_excludes_group_and_machine_specific_data(self) -> None:
        sanitized = sanitize_pipeline_state_for_preset(self.sample_pipeline())
        self.assertNotIn('local_config', sanitized['generation'])
        profile = sanitized['generation']['generation_profile']
        self.assertNotIn('reference_image', profile)
        self.assertNotIn('motion_video', profile)
        self.assertEqual(profile['steps'], 30)
        self.assertNotIn('selected_frames', sanitized['selection'])
        self.assertNotIn('start_frame', sanitized['selection']['smart_selection'])
        self.assertNotIn('end_frame', sanitized['selection']['smart_selection'])
        self.assertNotIn('r1_selection', sanitized['selection']['smart_selection'])
        self.assertNotIn('cleanup', sanitized)
        self.assertNotIn('frame_states', sanitized['alignment'])

    def test_merge_preserves_per_group_state(self) -> None:
        current = self.sample_pipeline()
        preset = build_production_preset(
            name='New',
            description='',
            pipeline_state={
                'generation': {'generation_profile': {'steps': 40, 'seed': 999}},
                'alignment': {'profile': {'canvas_width': 48, 'canvas_height': 48}},
                'export': {'studio': {'sheet_columns': 4}},
            },
            sections=['generation', 'alignment', 'export'],
        )
        merged = merge_preset_into_pipeline(current, preset)
        self.assertEqual(merged['generation']['generation_profile']['steps'], 40)
        self.assertEqual(merged['generation']['generation_profile']['seed'], 999)
        self.assertEqual(merged['generation']['local_config']['python_executable'], 'C:/private/python.exe')
        self.assertEqual(merged['selection']['selected_frames'], [1, 5, 9])
        self.assertEqual(merged['alignment']['frame_states']['1']['frame_index'], 1)
        self.assertEqual(merged['alignment']['profile']['canvas_width'], 48)
        self.assertEqual(merged['export']['studio']['source_mode'], 'aligned')
        self.assertEqual(merged['export']['studio']['sheet_columns'], 4)

    def test_starter_presets_do_not_impose_generation_settings(self) -> None:
        presets = starter_presets()
        walk = presets['Starter · Walk · 96×96']
        self.assertTrue(walk['builtin'])
        self.assertTrue(walk['calibration_required'])
        self.assertNotIn('generation', walk['pipeline_state'])
        self.assertEqual(walk['pipeline_state']['alignment']['profile']['canvas_width'], 96)
        self.assertEqual(presets['Starter · Small · 48×48']['pipeline_state']['alignment']['profile']['canvas_width'], 48)
        self.assertEqual(presets['Starter · Small · 36×36']['pipeline_state']['alignment']['profile']['canvas_width'], 36)

    def test_store_roundtrip_and_builtin_protection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profiles = ProfilesStore(Path(tmp) / 'profiles.json')
            store = ProductionPresetStore(profiles)
            self.assertIn('Starter · Walk · 96×96', store.list_names())
            custom = build_production_preset(
                name='Calibrated Walk',
                description='test',
                pipeline_state=self.sample_pipeline(),
                sections=['generation', 'alignment', 'export'],
            )
            store.save('Calibrated Walk', custom)
            loaded = store.get('Calibrated Walk')
            self.assertIsNotNone(loaded)
            self.assertFalse(loaded['builtin'])
            copy = store.duplicate('Calibrated Walk', 'Calibrated Walk copy')
            self.assertEqual(copy['name'], 'Calibrated Walk copy')
            store.delete('Calibrated Walk copy')
            self.assertIsNone(store.get('Calibrated Walk copy'))
            with self.assertRaises(ValueError):
                store.delete('Starter · Walk · 96×96')


if __name__ == '__main__':
    unittest.main()
