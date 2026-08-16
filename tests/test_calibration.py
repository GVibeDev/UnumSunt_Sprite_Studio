from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.calibration import (
    build_manual_run,
    build_run_from_job,
    build_single_parameter_variant,
    compare_generation_profiles,
    normalize_calibration_state,
    parse_variant_value,
    sync_jobs_to_runs,
)
from app.project_store import ProjectStore


class CalibrationCoreTests(unittest.TestCase):
    def _job(self, job_id: str = 'job_001') -> dict:
        return {
            'job_id': job_id,
            'provider': 'local_wangp',
            'model': 'wangp_template_model',
            'state': 'completed',
            'job_directory': f'/tmp/{job_id}',
            'started_at_utc': '2026-08-13T05:00:00+00:00',
            'completed_at_utc': '2026-08-13T05:02:00+00:00',
            'duration_seconds': 120.0,
            'request': {
                'provider': 'local_wangp',
                'model': 'wangp_template_model',
                'inputs': {'reference_image': '/ref.png', 'motion_video': '/motion.mp4'},
                'prompt': {'positive': 'walk cycle', 'negative': 'camera movement'},
                'generation': {'seed': 123, 'width': 480, 'height': 832, 'frames': 21, 'fps': 24.0, 'steps': 30},
                'metadata': {
                    'requested_resolution_class': '480p',
                    'requested_aspect_ratio': '9:16',
                    'requested_frames': 24,
                    'requested_fps': 24.0,
                    'requested_background_rgb': [0, 255, 0],
                },
            },
            'result': {
                'job_id': job_id,
                'state': 'completed',
                'provider': 'local_wangp',
                'model': 'wangp_template_model',
                'video_path': f'/tmp/{job_id}/output/out.mp4',
                'seed': 123,
                'metadata': {
                    'actual_width': 480,
                    'actual_height': 832,
                    'actual_frames': 21,
                    'actual_fps': 24.0,
                    'resolution_match': True,
                    'frames_match': True,
                    'fps_match': True,
                },
                'error_code': None,
                'error_message': None,
            },
        }

    def test_build_run_from_job_preserves_requested_profile_and_actual_result(self) -> None:
        run = build_run_from_job(self._job(), environment={'os': 'test'})
        profile = run['generation_profile']
        self.assertEqual(profile['seed'], 123)
        self.assertEqual(profile['resolution_class'], '480p')
        self.assertEqual(profile['aspect_ratio'], '9:16')
        self.assertEqual(profile['frames'], 24)
        self.assertEqual(profile['steps'], 30)
        self.assertEqual(run['result']['actual_frames'], 21)
        self.assertEqual(run['result']['duration_seconds'], 120.0)

    def test_sync_jobs_deduplicates_by_job_id(self) -> None:
        state, added = sync_jobs_to_runs(None, [self._job(), self._job()], environment={'os': 'test'})
        self.assertEqual(len(added), 1)
        self.assertEqual(len(state['runs']), 1)
        state2, added2 = sync_jobs_to_runs(state, [self._job()], environment={'os': 'test'})
        self.assertEqual(added2, [])
        self.assertEqual(len(state2['runs']), 1)

    def test_single_parameter_variant_preserves_seed_when_steps_change(self) -> None:
        base = build_run_from_job(self._job(), environment={'os': 'test'})['generation_profile']
        variant, change = build_single_parameter_variant(base, 'steps', 40)
        self.assertEqual(variant['steps'], 40)
        self.assertEqual(variant['seed'], base['seed'])
        self.assertTrue(change['seed_preserved'])
        self.assertEqual(set(compare_generation_profiles(base, variant)), {'steps'})

    def test_parse_variant_values(self) -> None:
        self.assertEqual(parse_variant_value('steps', '35'), 35)
        self.assertEqual(parse_variant_value('fps', '12.5'), 12.5)
        self.assertEqual(parse_variant_value('resolution_class', '720p'), '720p')
        with self.assertRaises(ValueError):
            parse_variant_value('frames', '0')

    def test_manual_run_is_configuration_only(self) -> None:
        run = build_manual_run({'seed': 9, 'steps': 20}, environment={'os': 'test'})
        self.assertEqual(run['source_kind'], 'manual_snapshot')
        self.assertEqual(run['result']['state'], 'configuration_only')
        self.assertEqual(run['generation_profile']['seed'], 9)

    def test_normalize_state_drops_missing_baseline(self) -> None:
        state = normalize_calibration_state({'baseline_run_id': 'missing', 'runs': []})
        self.assertIsNone(state['baseline_run_id'])

    def test_project_store_calibration_roundtrip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / 'project'
            store = ProjectStore.create(project_dir, name='Calibration Project')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Walk', parent_id=subject['id'])
            direction = store.create_group(group_type='direction', name='SE', parent_id=animation['id'])
            state = {'schema': 'test', 'baseline_run_id': None, 'runs': [{'id': 'run1'}]}
            store.set_group_calibration(direction['id'], state)
            loaded = store.get_group_calibration(direction['id'])
            self.assertEqual(loaded['runs'][0]['id'], 'run1')


if __name__ == '__main__':
    unittest.main()
