from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

try:
    from app.project_session import ProjectSession
    from app.project_store import ProjectStore
    QT_AVAILABLE = True
except ModuleNotFoundError as exc:  # pragma: no cover - packaging interpreter may lack PySide6
    if exc.name != 'PySide6':
        raise
    ProjectSession = None  # type: ignore[assignment]
    ProjectStore = None  # type: ignore[assignment]
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, 'PySide6 is required for ProjectSession signal tests.')
class ProjectSessionRuntimeStateTests(unittest.TestCase):
    def _project_with_direction(self, root: Path):
        store = ProjectStore.create(root, name='Demo')
        subject = store.create_group(group_type='subject', name='Hero')
        animation = store.create_group(group_type='animation', name='Walk', parent_id=subject['id'])
        direction = store.create_group(group_type='direction', name='E', parent_id=animation['id'])
        store.set_active_group(direction['id'])
        return subject, animation, direction

    def test_open_project_scopes_runtime_state_without_copying_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            _subject, _animation, direction = self._project_with_direction(root)
            session = ProjectSession()
            session.open_project(root)
            self.assertEqual(session.project_state.active_group_id, direction['id'])
            snapshot = session.project_state.diagnostic_snapshot()
            self.assertNotIn('groups', snapshot)
            self.assertNotIn('pipeline_state', snapshot)

    def test_context_comes_from_store_lineage_plus_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            _subject, _animation, _direction = self._project_with_direction(root)
            session = ProjectSession()
            session.open_project(root)
            session.set_current_asset('sprite-01')
            session.set_current_frame(2)
            context = session.project_context
            self.assertEqual(context.breadcrumb_labels, ('Hero', 'Walk', 'E'))
            self.assertEqual(context.asset_id, 'sprite-01')
            self.assertEqual(context.frame_index, 2)

    def test_active_direction_change_invalidates_old_runtime_production_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            _subject, animation, first = self._project_with_direction(root)
            store = ProjectStore.open(root)
            second = store.create_group(group_type='direction', name='W', parent_id=animation['id'])
            session = ProjectSession()
            session.open_project(root)
            session.set_current_source(kind='video', path='walk.mp4')
            session.set_current_frame(5)
            session.set_selected_frames([2, 5])

            session.set_active_group(second['id'])

            self.assertEqual(session.project_state.active_group_id, second['id'])
            self.assertIsNone(session.project_state.current_source)
            self.assertIsNone(session.project_state.current_frame_index)
            self.assertEqual(session.project_state.selected_frames, ())
            self.assertNotEqual(first['id'], second['id'])

    def test_runtime_state_signal_is_not_emitted_for_noop_update(self) -> None:
        session = ProjectSession()
        changes: list[int] = []
        session.project_state_changed.connect(lambda: changes.append(1))
        session.set_current_frame(None)
        self.assertEqual(changes, [])
        session.set_current_frame(0)
        self.assertEqual(changes, [1])


if __name__ == '__main__':
    unittest.main()
