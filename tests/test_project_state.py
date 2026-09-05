from __future__ import annotations

import unittest

from app.create_workspace_state import CreateViewState, CreateWorkspaceState, ToolState
from app.project_state import ProjectState, SourceRef


class ProjectStateTests(unittest.TestCase):
    def test_initial_state_is_empty_and_not_a_project_document_cache(self) -> None:
        state = ProjectState()
        self.assertIsNone(state.project_path)
        self.assertIsNone(state.active_group_id)
        self.assertIsNone(state.current_source)
        self.assertEqual(state.selected_frames, ())
        self.assertNotIn('pipeline_state', state.diagnostic_snapshot())
        self.assertNotIn('groups', state.diagnostic_snapshot())

    def test_project_adoption_resets_production_context(self) -> None:
        state = ProjectState()
        state.adopt_project('A', 'dir_a')
        state.set_current_asset('asset-a')
        state.set_current_source(SourceRef(kind='video', path='walk.mp4'))
        state.set_current_frame(4)
        state.set_selected_frames([4, 2, 4])

        state.adopt_project('B', 'dir_b')

        self.assertEqual(state.project_path, 'B')
        self.assertEqual(state.active_group_id, 'dir_b')
        self.assertIsNone(state.current_asset_id)
        self.assertIsNone(state.current_source)
        self.assertIsNone(state.current_frame_index)
        self.assertEqual(state.selected_frames, ())

    def test_reopening_same_project_scope_still_clears_runtime_source_state(self) -> None:
        state = ProjectState()
        state.adopt_project('A', 'dir_a')
        state.set_current_source(SourceRef(kind='video', path='walk.mp4'))
        state.set_current_frame(4)

        state.adopt_project('A', 'dir_a')

        self.assertEqual(state.project_path, 'A')
        self.assertEqual(state.active_group_id, 'dir_a')
        self.assertIsNone(state.current_source)
        self.assertIsNone(state.current_frame_index)

    def test_group_change_resets_only_group_scoped_production_context(self) -> None:
        state = ProjectState(project_path='A', active_group_id='dir_a')
        state.set_current_asset('asset-a')
        state.set_current_source(SourceRef(kind='sequence', path='frames'))
        state.set_current_frame(3)
        state.set_selected_frames([1, 3])

        state.set_active_group('dir_b')

        self.assertEqual(state.project_path, 'A')
        self.assertEqual(state.active_group_id, 'dir_b')
        self.assertIsNone(state.current_source)
        self.assertEqual(state.selected_frames, ())

    def test_source_change_cannot_keep_stale_frame_identity(self) -> None:
        state = ProjectState(project_path='A', active_group_id='dir_a')
        state.set_current_source(SourceRef(kind='video', path='walk.mp4'))
        state.set_current_frame(7)
        state.set_selected_frames([1, 7])

        state.set_current_source(SourceRef(kind='sequence', path='idle-frames'))

        self.assertIsNone(state.current_frame_index)
        self.assertEqual(state.selected_frames, ())

    def test_frame_selection_is_normalized_and_negative_values_are_rejected(self) -> None:
        state = ProjectState()
        state.set_selected_frames([7, 1, 7, 3])
        self.assertEqual(state.selected_frames, (1, 3, 7))
        with self.assertRaises(ValueError):
            state.set_selected_frames([0, -1])
        with self.assertRaises(ValueError):
            state.set_current_frame(-1)

    def test_context_breadcrumb_uses_real_group_lineage(self) -> None:
        state = ProjectState(project_path='demo', active_group_id='d')
        state.set_current_asset('sprite-asset')
        state.set_current_frame(5)
        context = state.context_from_lineage([
            {'id': 's', 'type': 'subject', 'name': 'Hero'},
            {'id': 'a', 'type': 'animation', 'name': 'Walk'},
            {'id': 'd', 'type': 'direction', 'name': 'East'},
        ])
        self.assertEqual(context.breadcrumb_labels, ('Hero', 'Walk', 'East'))
        self.assertEqual(context.asset_id, 'sprite-asset')
        self.assertEqual(context.frame_index, 5)

    def test_context_exposes_runtime_source_name_without_copying_source_payload(self) -> None:
        state = ProjectState(project_path='demo', active_group_id='d')
        state.set_current_source(SourceRef(kind='video', path='C:/assets/walk.mp4'))
        state.set_current_frame(2)
        context = state.context_from_lineage([])
        self.assertEqual(context.source_kind, 'video')
        self.assertEqual(context.source_name, 'walk.mp4')
        self.assertEqual(context.frame_index, 2)


class CreateWorkspaceStateTests(unittest.TestCase):
    def test_view_state_keeps_pan_zoom_and_panel_presentation_separate(self) -> None:
        state = CreateViewState()
        state.set_view_transform(pan_x=12.5, pan_y=-4.0, zoom=2.0)
        state.set_panel_widths(left=280, right=340)
        state.left_panel_section = 'brush-options'
        state.right_panel_section = 'export'
        self.assertEqual((state.pan_x, state.pan_y, state.zoom), (12.5, -4.0, 2.0))
        self.assertEqual((state.left_panel_width, state.right_panel_width), (280, 340))
        self.assertEqual(state.left_panel_section, 'brush-options')
        self.assertEqual(state.right_panel_section, 'export')

    def test_view_state_rejects_invalid_zoom_and_panel_sizes(self) -> None:
        state = CreateViewState()
        with self.assertRaises(ValueError):
            state.set_view_transform(pan_x=0, pan_y=0, zoom=0)
        with self.assertRaises(ValueError):
            state.set_panel_widths(left=0)

    def test_tool_state_has_explicit_neutral_state(self) -> None:
        state = ToolState()
        self.assertFalse(state.has_active_tool)
        state.activate('brush')
        self.assertTrue(state.has_active_tool)
        self.assertEqual(state.active_tool_id, 'brush')
        state.deactivate()
        self.assertFalse(state.has_active_tool)

    def test_workspace_state_does_not_persist_a_tool_by_default(self) -> None:
        first = CreateWorkspaceState()
        first.tool.activate('brush')
        second = CreateWorkspaceState()
        self.assertIsNone(second.tool.active_tool_id)


if __name__ == '__main__':
    unittest.main()
