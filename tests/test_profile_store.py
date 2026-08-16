from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.profile_store import ProfilesStore


class ProfileStoreTests(unittest.TestCase):
    def test_named_profile_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProfilesStore(Path(tmp) / 'profiles.json')
            payload = {'tolerance': 42, 'background_rgb': [1, 2, 3]}
            store.set_profile('chroma', 'desert', payload)
            self.assertEqual(store.list_profiles('chroma'), ['desert'])
            self.assertEqual(store.get_profile('chroma', 'desert'), payload)

    def test_last_used_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProfilesStore(Path(tmp) / 'profiles.json')
            payload = {'canvas_width': 96, 'canvas_height': 96}
            store.set_last_used('alignment', payload)
            self.assertEqual(store.get_last_used('alignment'), payload)


    def test_generation_profile_and_app_state_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProfilesStore(Path(tmp) / 'profiles.json')
            generation = {'steps': 30, 'resolution_class': '480p'}
            app_state = {'current_tab': 2, 'current_project_path': '/tmp/demo'}
            store.set_profile('generation', 'walk-480', generation)
            self.assertEqual(store.get_profile('generation', 'walk-480'), generation)
            store.set_last_used('generation', generation)
            self.assertEqual(store.get_last_used('generation'), generation)
            store.set_app_state(app_state)
            self.assertEqual(store.get_app_state(), app_state)

    def test_advanced_chroma_profile_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProfilesStore(Path(tmp) / 'profiles.json')
            payload = {
                'background_rgb': [0, 255, 0],
                'outer_border_mask_px': 12,
                'subject_edge_mask_expand_px': 3,
                'additional_background_colors': [{'rgb': [20, 30, 40], 'enabled': True, 'tolerance': 18}],
            }
            store.set_profile('chroma', 'advanced-mask', payload)
            self.assertEqual(store.get_profile('chroma', 'advanced-mask'), payload)

    def test_delete_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProfilesStore(Path(tmp) / 'profiles.json')
            store.set_profile('alignment', 'iso96', {'canvas_width': 96})
            store.delete_profile('alignment', 'iso96')
            self.assertEqual(store.list_profiles('alignment'), [])
            self.assertIsNone(store.get_profile('alignment', 'iso96'))


if __name__ == '__main__':
    unittest.main()
