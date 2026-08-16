from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.project_store import PROJECT_FILENAME, ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def test_create_project_scaffold_and_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'hero_walk'
            store = ProjectStore.create(root, name='Hero Walk', subject='Hero')
            self.assertTrue((root / PROJECT_FILENAME).exists())
            self.assertTrue((root / 'generations').is_dir())
            payload = store.load()
            self.assertEqual(payload['name'], 'Hero Walk')
            self.assertEqual(payload['subject'], 'Hero')
            payload['assets']['reference_image'] = 'source/hero.png'
            payload['pipeline_state']['selection'] = {'selected_frames': [0, 1, 2]}
            store.save(payload)
            reopened = ProjectStore.open(root)
            loaded = reopened.load()
            self.assertEqual(loaded['assets']['reference_image'], 'source/hero.png')
            self.assertEqual(loaded['pipeline_state']['selection']['selected_frames'], [0, 1, 2])

    def test_append_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'hero_idle'
            store = ProjectStore.create(root)
            store.append_job({'job_id': 'walk_001', 'state': 'completed'})
            payload = store.load()
            self.assertEqual(len(payload['jobs']), 1)
            self.assertEqual(payload['jobs'][0]['job_id'], 'walk_001')


if __name__ == '__main__':
    unittest.main()
