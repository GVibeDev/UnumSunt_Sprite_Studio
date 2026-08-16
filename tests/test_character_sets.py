from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.character_sets import (
    DIRECTIONS,
    add_layer,
    character_set_coverage,
    inspect_layer_source,
    layer_assignment_coverage,
    move_layer,
    new_character_set_state,
    normalize_character_set_state,
    remove_layer,
    update_layer,
)
from app.project_store import ProjectStore


class CharacterSetPureTests(unittest.TestCase):
    def test_layer_lifecycle(self) -> None:
        state, layer = add_layer(new_character_set_state(), 'Mantello', kind='outfit')
        state = update_layer(state, layer['id'], opacity=0.5, export_enabled=False, notes='cloth')
        self.assertEqual(state['layers'][0]['name'], 'Mantello')
        self.assertEqual(state['layers'][0]['kind'], 'outfit')
        self.assertAlmostEqual(state['layers'][0]['opacity'], 0.5)
        self.assertFalse(state['layers'][0]['export_enabled'])
        state = remove_layer(state, layer['id'])
        self.assertEqual(state['layers'], [])

    def test_move_layer_reorders_deterministically(self) -> None:
        state, a = add_layer(new_character_set_state(), 'A')
        state, b = add_layer(state, 'B')
        state = move_layer(state, b['id'], -1)
        self.assertEqual([layer['name'] for layer in state['layers']], ['B', 'A'])
        self.assertEqual([layer['order'] for layer in state['layers']], [0, 1])

    def test_normalize_unknown_kind_and_clamps_opacity(self) -> None:
        state = normalize_character_set_state({'layers': [{'id': 'x', 'name': 'X', 'kind': 'alien', 'opacity': 4}]})
        self.assertEqual(state['layers'][0]['kind'], 'custom')
        self.assertEqual(state['layers'][0]['opacity'], 1.0)

    def test_coverage_tracks_all_eight_directions(self) -> None:
        groups = [
            {'id': 's', 'type': 'subject', 'name': 'Hero', 'parent_id': None},
            {'id': 'a', 'type': 'animation', 'name': 'Walk', 'parent_id': 's'},
            {'id': 'd1', 'type': 'direction', 'name': 'N', 'parent_id': 'a', 'status': 'aligned', 'metadata': {'direction': 'N'}},
            {'id': 'd2', 'type': 'direction', 'name': 'SE', 'parent_id': 'a', 'status': 'generated', 'metadata': {'direction': 'SE'}},
        ]
        result = character_set_coverage(groups, 's')
        self.assertEqual(result['total_slots'], len(DIRECTIONS))
        self.assertEqual(result['present_slots'], 2)
        self.assertEqual(result['ready_slots'], 1)
        self.assertEqual(len(result['rows'][0]['directions']), 8)

    def test_layer_assignment_coverage(self) -> None:
        groups = [
            {'id': 's', 'type': 'subject', 'name': 'Hero', 'parent_id': None},
            {'id': 'a', 'type': 'animation', 'name': 'Walk', 'parent_id': 's'},
            {'id': 'd1', 'type': 'direction', 'name': 'N', 'parent_id': 'a', 'metadata': {'layer_stack': {'assignments': {'l1': {'manifest_path': '/tmp/a.json'}}}}},
            {'id': 'd2', 'type': 'direction', 'name': 'S', 'parent_id': 'a', 'metadata': {}},
        ]
        result = layer_assignment_coverage(groups, 's', ['l1', 'l2'])
        self.assertEqual(result['direction_count'], 2)
        self.assertEqual(result['assigned_by_layer']['l1'], 1)
        self.assertEqual(result['assigned_by_layer']['l2'], 0)

    def test_layer_sequence_rejects_mixed_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGBA', (16, 16), (255, 0, 0, 128)).save(root / 'a.png')
            Image.new('RGBA', (17, 16), (255, 0, 0, 128)).save(root / 'b.png')
            with self.assertRaises(ValueError):
                inspect_layer_source(root)

    def test_layer_sequence_reports_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new('RGBA', (16, 16), (255, 0, 0, 128)).save(root / 'a.png')
            Image.new('RGBA', (16, 16), (0, 255, 0, 128)).save(root / 'b.png')
            result = inspect_layer_source(root)
            self.assertEqual(result['mode'], 'sequence')
            self.assertEqual(result['frame_count'], 2)
            self.assertTrue(result['has_alpha'])


class CharacterSetProjectStoreTests(unittest.TestCase):
    def _make_project(self, root: Path) -> tuple[ProjectStore, dict, dict, dict]:
        store = ProjectStore.create(root, name='Test')
        subject = store.create_group(group_type='subject', name='Hero')
        animation = store.create_group(group_type='animation', name='Walk', parent_id=subject['id'])
        direction = store.create_group(group_type='direction', name='SE', parent_id=animation['id'], metadata={'direction': 'SE'})
        return store, subject, animation, direction

    def test_character_set_persists_on_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store, subject, _, _ = self._make_project(Path(tmp))
            layer = store.add_character_layer(subject['id'], 'Weapon', kind='equipment')
            reopened = ProjectStore.open(Path(tmp))
            state = reopened.get_character_set(subject['id'])
            self.assertEqual(state['layers'][0]['id'], layer['id'])
            self.assertEqual(state['layers'][0]['kind'], 'equipment')

    def test_import_direction_layer_copies_file_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / 'project'
            store, subject, _, direction = self._make_project(project)
            layer = store.add_character_layer(subject['id'], 'Cape', kind='outfit')
            source = root / 'cape.png'
            Image.new('RGBA', (24, 32), (10, 20, 30, 120)).save(source)
            assignment = store.import_direction_layer_asset(direction['id'], layer['id'], source)
            self.assertTrue(Path(assignment['manifest_path']).exists())
            self.assertEqual(assignment['width'], 24)
            self.assertEqual(assignment['height'], 32)
            manifest = json.loads(Path(assignment['manifest_path']).read_text(encoding='utf-8'))
            self.assertEqual(manifest['layer_id'], layer['id'])
            self.assertEqual(manifest['frame_count'], 1)

    def test_assignment_offsets_are_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, subject, _, direction = self._make_project(root / 'project')
            layer = store.add_character_layer(subject['id'], 'FX', kind='effect')
            source = root / 'fx.png'
            Image.new('RGBA', (8, 8), (255, 255, 255, 50)).save(source)
            store.import_direction_layer_asset(direction['id'], layer['id'], source)
            store.update_direction_layer_assignment(direction['id'], layer['id'], offset_x=4, offset_y=-3, visible=False)
            stack = store.get_direction_layer_stack(direction['id'])
            assignment = stack['assignments'][layer['id']]
            self.assertEqual(assignment['offset_x'], 4)
            self.assertEqual(assignment['offset_y'], -3)
            self.assertFalse(assignment['visible'])

    def test_remove_character_layer_cleans_direction_assignments_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, subject, _, direction = self._make_project(root / 'project')
            layer = store.add_character_layer(subject['id'], 'FX', kind='effect')
            source = root / 'fx.png'
            Image.new('RGBA', (8, 8), (255, 255, 255, 50)).save(source)
            store.import_direction_layer_asset(direction['id'], layer['id'], source)
            layer_dir = store.group_workspace(direction['id']) / 'layers' / layer['id']
            self.assertTrue(layer_dir.exists())
            store.remove_character_layer(subject['id'], layer['id'])
            self.assertFalse(layer_dir.exists())
            self.assertNotIn(layer['id'], store.get_direction_layer_stack(direction['id'])['assignments'])

    def test_duplicate_direction_remaps_layer_manifest_into_clone_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, subject, _, direction = self._make_project(root / 'project')
            layer = store.add_character_layer(subject['id'], 'FX', kind='effect')
            source = root / 'fx.png'
            Image.new('RGBA', (8, 8), (255, 255, 255, 50)).save(source)
            store.import_direction_layer_asset(direction['id'], layer['id'], source)
            clone = store.duplicate_group(direction['id'])
            stack = store.get_direction_layer_stack(clone['id'])
            manifest = Path(stack['assignments'][layer['id']]['manifest_path'])
            self.assertTrue(manifest.exists())
            self.assertIn(clone['id'], manifest.as_posix())

    def test_copy_group_data_copies_layer_stack_and_remaps_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, subject, animation, source_direction = self._make_project(root / 'project')
            target_direction = store.create_group(group_type='direction', name='SW', parent_id=animation['id'], metadata={'direction': 'SW'})
            layer = store.add_character_layer(subject['id'], 'FX', kind='effect')
            source = root / 'fx.png'
            Image.new('RGBA', (8, 8), (255, 255, 255, 50)).save(source)
            store.import_direction_layer_asset(source_direction['id'], layer['id'], source)
            store.copy_group_data(source_direction['id'], target_direction['id'])
            stack = store.get_direction_layer_stack(target_direction['id'])
            manifest = Path(stack['assignments'][layer['id']]['manifest_path'])
            self.assertTrue(manifest.exists())
            self.assertIn(target_direction['id'], manifest.as_posix())


if __name__ == '__main__':
    unittest.main()
