from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.project_store import ProjectStore


class ProjectGroupTests(unittest.TestCase):
    def _make_direction(self, store: ProjectStore, subject='Hero', animation='Walk', direction='SE'):
        s = store.create_group(group_type='subject', name=subject)
        a = store.create_group(group_type='animation', name=animation, parent_id=s['id'])
        d = store.create_group(group_type='direction', name=direction, parent_id=a['id'], metadata={'direction': direction})
        return s, a, d

    def test_hierarchy_active_group_and_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore.create(Path(tmp) / 'project')
            subject, animation, direction = self._make_direction(store)
            self.assertEqual(store.group_label(direction['id']), 'Hero / Walk / SE')
            with self.assertRaises(ValueError):
                store.set_active_group(animation['id'])
            store.set_active_group(direction['id'])
            active = store.get_active_group()
            self.assertIsNotNone(active)
            self.assertEqual(active['id'], direction['id'])
            workspace = store.group_workspace(direction['id'])
            self.assertTrue((workspace / 'cleanup').is_dir())
            self.assertTrue((workspace / 'exports').is_dir())

    def test_group_snapshot_promotes_status_and_isolated_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore.create(Path(tmp) / 'project')
            _, _, direction = self._make_direction(store)
            snapshot = {
                'assets': {
                    'reference_image': 'hero.png',
                    'motion_reference': 'walk.mp4',
                    'source_video': 'generated.mp4',
                },
                'pipeline_state': {
                    'selection': {'selected_frames': [1, 5, 9]},
                    'cleanup': {'frame_indices': [1]},
                    'alignment': {'frame_states': {'1': {'frame_index': 1}}},
                    'generation': {'generation_profile': {'steps': 30}},
                    'chroma': {'tolerance': 20},
                    'export': {},
                },
            }
            store.update_group_snapshot(direction['id'], snapshot)
            group = store.get_group(direction['id'])
            self.assertEqual(group['assets']['source_video'], 'generated.mp4')
            self.assertEqual(group['pipeline_state']['selection']['selected_frames'], [1, 5, 9])
            self.assertEqual(group['status'], 'aligned')
            project = store.load()
            self.assertIsNone(project['assets']['source_video'])

    def test_append_job_and_export_advance_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore.create(Path(tmp) / 'project')
            _, _, direction = self._make_direction(store)
            store.update_group_snapshot(direction['id'], {
                'assets': {'source_sequence_manifest': 'old-sequence.json', 'source_spritesheet': 'old-sheet.png'},
                'pipeline_state': {},
            })
            store.append_group_job(direction['id'], {
                'job_id': 'job-1',
                'result': {'state': 'completed', 'video_path': 'video.mp4'},
            })
            group = store.get_group(direction['id'])
            self.assertEqual(group['status'], 'generated')
            self.assertEqual(group['assets']['source_video'], 'video.mp4')
            self.assertIsNone(group['assets']['source_sequence_manifest'])
            self.assertIsNone(group['assets']['source_spritesheet'])
            store.append_group_export(direction['id'], {'output_directory': 'exports/final'})
            group = store.get_group(direction['id'])
            self.assertEqual(group['status'], 'exported')
            self.assertEqual(len(group['exports']), 1)

    def test_duplicate_subtree_and_delete_are_recursive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore.create(Path(tmp) / 'project')
            subject, animation, direction = self._make_direction(store)
            cleanup_path = store.group_workspace(direction['id']) / 'cleanup' / 'marker.txt'
            cleanup_path.write_text('persist me', encoding='utf-8')
            clone = store.duplicate_group(animation['id'])
            self.assertEqual(clone['type'], 'animation')
            children = store.children_of(clone['id'])
            self.assertEqual(len(children), 1)
            cloned_direction = children[0]
            self.assertTrue((store.group_workspace(cloned_direction['id']) / 'cleanup' / 'marker.txt').exists())
            store.set_active_group(direction['id'])
            store.delete_group(subject['id'])
            self.assertEqual(store.list_groups(), [])
            self.assertIsNone(store.get_active_group())

    def test_copy_direction_data_copies_cleanup_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore.create(Path(tmp) / 'project')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Walk', parent_id=subject['id'])
            source = store.create_group(group_type='direction', name='SE', parent_id=animation['id'])
            target = store.create_group(group_type='direction', name='SW', parent_id=animation['id'])
            np.savez_compressed(store.group_workspace(source['id']) / 'cleanup' / 'rgba_overrides.npz', frame_1=np.zeros((2, 2, 4), dtype=np.uint8))
            store.update_group_snapshot(source['id'], {
                'assets': {'reference_image': 'hero.png'},
                'pipeline_state': {'cleanup': {'frame_indices': [1], 'override_file': 'cleanup/rgba_overrides.npz'}},
            })
            store.copy_group_data(source['id'], target['id'])
            target_group = store.get_group(target['id'])
            self.assertEqual(target_group['assets']['reference_image'], 'hero.png')
            self.assertTrue((store.group_workspace(target['id']) / 'cleanup' / 'rgba_overrides.npz').exists())


    def test_copy_direction_remaps_internal_sequence_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore.create(Path(tmp) / 'project')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Walk', parent_id=subject['id'])
            source = store.create_group(group_type='direction', name='SE', parent_id=animation['id'])
            target = store.create_group(group_type='direction', name='SW', parent_id=animation['id'])
            source_workspace = store.group_workspace(source['id'])
            manifest = source_workspace / 'spritesheet_import' / 'import_manifest.json'
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text('{"kind":"sprite_sequence"}', encoding='utf-8')
            store.update_group_snapshot(source['id'], {
                'assets': {
                    'source_sequence_manifest': str(manifest.resolve()),
                    'source_spritesheet': '/external/sheet.png',
                },
                'pipeline_state': {},
            })
            store.copy_group_data(source['id'], target['id'])
            copied = store.get_group(target['id'])
            expected = store.group_workspace(target['id']) / 'spritesheet_import' / 'import_manifest.json'
            self.assertEqual(Path(copied['assets']['source_sequence_manifest']), expected.resolve())
            self.assertEqual(copied['assets']['source_spritesheet'], '/external/sheet.png')
            self.assertTrue(expected.exists())

    def test_old_project_without_group_fields_migrates_in_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            store = ProjectStore.create(root)
            payload = store.load()
            payload.pop('active_group_id', None)
            payload['version'] = 'R5e3'
            store.path.write_text(__import__('json').dumps(payload), encoding='utf-8')
            migrated = store.load()
            self.assertEqual(migrated['version'], 'R5c3')
            self.assertIsNone(migrated['active_group_id'])
            self.assertEqual(migrated['groups'], [])

    def test_assign_production_preset_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore.create(Path(tmp) / 'project')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Walk', parent_id=subject['id'])
            direction = store.create_group(group_type='direction', name='SE', parent_id=animation['id'])
            store.assign_production_preset(direction['id'], 'Calibrated Walk', sections=['generation', 'alignment'])
            group = store.get_group(direction['id'])
            assignment = group['metadata']['production_preset']
            self.assertEqual(assignment['name'], 'Calibrated Walk')
            self.assertEqual(assignment['sections'], ['generation', 'alignment'])
            store.clear_production_preset_assignment(direction['id'])
            group = store.get_group(direction['id'])
            self.assertNotIn('production_preset', group['metadata'])


if __name__ == '__main__':
    unittest.main()
