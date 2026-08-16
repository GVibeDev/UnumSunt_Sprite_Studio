from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.project_store import ProjectStore
from app.workflows import (
    WORKFLOW_DEFINITIONS,
    inferred_completed_steps,
    new_workflow_state,
    next_incomplete_step,
    normalize_workflow_state,
    set_step_state,
    step_statuses,
)


class WorkflowDefinitionTests(unittest.TestCase):
    def test_three_official_workflows_exist(self) -> None:
        self.assertEqual(set(WORKFLOW_DEFINITIONS), {'standard', 'full', 'spritesheet_rework'})

    def test_standard_order(self) -> None:
        ids = [step['id'] for step in WORKFLOW_DEFINITIONS['standard']['steps']]
        self.assertEqual(ids, [
            'video_generation', 'frame_selection', 'cleanup', 'alignment', 'settings_checkpoint', 'export'
        ])

    def test_full_order(self) -> None:
        ids = [step['id'] for step in WORKFLOW_DEFINITIONS['full']['steps']]
        self.assertEqual(ids[:4], ['image_generation', 'spritesheet_import', 'motion_reference', 'final_video_generation'])
        self.assertEqual(ids[-5:], ['frame_selection', 'cleanup', 'alignment', 'settings_checkpoint', 'export'])

    def test_rework_has_no_generation_steps(self) -> None:
        ids = [step['id'] for step in WORKFLOW_DEFINITIONS['spritesheet_rework']['steps']]
        self.assertNotIn('video_generation', ids)
        self.assertNotIn('image_generation', ids)
        self.assertEqual(ids[0], 'spritesheet_import')


class WorkflowStateTests(unittest.TestCase):
    def test_new_and_normalize(self) -> None:
        state = new_workflow_state('full')
        self.assertEqual(state['type'], 'full')
        self.assertEqual(state['current_step'], 'image_generation')
        normalized = normalize_workflow_state(state)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized['type'], 'full')

    def test_set_step_state(self) -> None:
        state = new_workflow_state('standard')
        state = set_step_state(state, 'video_generation', 'complete')
        self.assertIn('video_generation', state['completed_steps'])
        state = set_step_state(state, 'video_generation', 'pending')
        self.assertNotIn('video_generation', state['completed_steps'])

    def test_standard_inference(self) -> None:
        workflow = new_workflow_state('standard')
        group = {
            'assets': {'source_video': '/tmp/final.mp4'},
            'pipeline_state': {
                'selection': {'selected_frames': [1, 2]},
                'cleanup': {'frame_indices': [1]},
                'alignment': {'frame_states': {'1': {}}},
            },
            'exports': [{'path': '/tmp/out'}],
            'status': 'exported',
            'metadata': {'workflow': workflow},
        }
        completed = inferred_completed_steps(group, workflow)
        self.assertTrue({'video_generation', 'frame_selection', 'cleanup', 'alignment', 'export'} <= completed)
        self.assertEqual(next_incomplete_step(group, workflow), 'settings_checkpoint')

    def test_full_final_generation_requires_new_source_after_motion_promotion(self) -> None:
        workflow = new_workflow_state('full')
        workflow['motion_reference'] = {
            'path': '/project/motion_references/motion.mp4',
            'promoted_from_source_video': '/project/generations/intermediate.mp4',
        }
        workflow = set_step_state(workflow, 'motion_reference', 'complete')
        group = {
            'assets': {
                'generated_image': '/project/source/generated_master.png',
                'source_spritesheet': '/project/source/move.png',
                'source_video': '/project/generations/intermediate.mp4',
                'motion_reference': '/project/motion_references/motion.mp4',
            },
            'pipeline_state': {},
            'exports': [],
            'status': 'generated',
            'metadata': {'workflow': workflow},
        }
        completed = inferred_completed_steps(group, workflow)
        self.assertIn('motion_reference', completed)
        self.assertNotIn('final_video_generation', completed)
        group['assets']['source_video'] = '/project/generations/final.mp4'
        completed = inferred_completed_steps(group, workflow)
        self.assertIn('final_video_generation', completed)

    def test_step_statuses_preserve_manual_skip(self) -> None:
        workflow = new_workflow_state('spritesheet_rework')
        workflow = set_step_state(workflow, 'cleanup', 'skipped')
        group = {'assets': {}, 'pipeline_state': {}, 'exports': [], 'status': 'missing', 'metadata': {'workflow': workflow}}
        statuses = {row['id']: row['status'] for row in step_statuses(group, workflow)}
        self.assertEqual(statuses['cleanup'], 'skipped')


class ProjectStoreWorkflowTests(unittest.TestCase):
    def test_workflow_roundtrip_on_direction_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore.create(Path(tmp) / 'project')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Walk', parent_id=subject['id'])
            direction = store.create_group(group_type='direction', name='SE', parent_id=animation['id'])
            state = new_workflow_state('standard')
            store.set_group_workflow(direction['id'], state)
            loaded = store.get_group_workflow(direction['id'])
            self.assertEqual(loaded['type'], 'standard')
            self.assertEqual(store.load()['version'], 'R5c3')
            store.clear_group_workflow(direction['id'])
            self.assertIsNone(store.get_group_workflow(direction['id']))


if __name__ == '__main__':
    unittest.main()
