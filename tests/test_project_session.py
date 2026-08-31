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
class ProjectSessionTests(unittest.TestCase):
    def test_initial_session_has_no_store_or_context(self) -> None:
        session = ProjectSession()
        self.assertIsNone(session.store)
        self.assertIsNone(session.project_path)
        self.assertIsNone(session.active_group_id)

    def test_create_project_adopts_single_authoritative_store_and_emits_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            events: list[str] = []
            session = ProjectSession()
            session.project_changed.connect(lambda path: events.append(path))

            store = session.create_project(root, name='Demo')

            self.assertIs(session.store, store)
            self.assertEqual(Path(session.project_path), root)
            self.assertEqual(events, [str(root)])
            self.assertIsNone(session.active_group_id)

    def test_open_project_restores_active_group_after_project_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            store = ProjectStore.create(root, name='Demo')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Idle', parent_id=subject['id'])
            direction = store.create_group(group_type='direction', name='S', parent_id=animation['id'])
            store.set_active_group(direction['id'])

            events: list[tuple[str, str]] = []
            session = ProjectSession()
            session.project_changed.connect(lambda path: events.append(('project', path)))
            session.active_group_changed.connect(lambda group_id: events.append(('group', group_id)))

            session.open_project(root)

            self.assertEqual(session.active_group_id, direction['id'])
            self.assertEqual(events[0], ('project', str(root)))
            self.assertEqual(events[1], ('group', direction['id']))

    def test_set_active_group_emits_will_change_then_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            store = ProjectStore.create(root, name='Demo')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Idle', parent_id=subject['id'])
            first = store.create_group(group_type='direction', name='S', parent_id=animation['id'])
            second = store.create_group(group_type='direction', name='N', parent_id=animation['id'])
            store.set_active_group(first['id'])

            session = ProjectSession()
            session.open_project(root)
            events: list[tuple[str, str, str]] = []
            session.active_group_will_change.connect(
                lambda old, new: events.append(('will', old, new))
            )
            session.active_group_changed.connect(
                lambda current: events.append(('changed', current, ''))
            )

            session.set_active_group(second['id'])

            self.assertEqual(session.active_group_id, second['id'])
            self.assertEqual(events[0], ('will', first['id'], second['id']))
            self.assertEqual(events[1], ('changed', second['id'], ''))

    def test_setting_same_active_group_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            store = ProjectStore.create(root, name='Demo')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Idle', parent_id=subject['id'])
            direction = store.create_group(group_type='direction', name='S', parent_id=animation['id'])
            store.set_active_group(direction['id'])
            session = ProjectSession()
            session.open_project(root)
            events: list[str] = []
            session.active_group_will_change.connect(lambda *_: events.append('will'))
            session.active_group_changed.connect(lambda *_: events.append('changed'))

            session.set_active_group(direction['id'])

            self.assertEqual(events, [])

    def test_non_direction_activation_is_rejected_without_changed_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            store = ProjectStore.create(root, name='Demo')
            subject = store.create_group(group_type='subject', name='Hero')
            session = ProjectSession()
            session.open_project(root)
            changed: list[str] = []
            will_change: list[tuple[str, str]] = []
            session.active_group_will_change.connect(lambda old, new: will_change.append((old, new)))
            session.active_group_changed.connect(changed.append)

            with self.assertRaises(ValueError):
                session.set_active_group(subject['id'])

            self.assertEqual(will_change, [])
            self.assertEqual(changed, [])
            self.assertIsNone(session.active_group_id)

    def test_synchronize_active_group_publishes_deletion_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            store = ProjectStore.create(root, name='Demo')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Idle', parent_id=subject['id'])
            direction = store.create_group(group_type='direction', name='S', parent_id=animation['id'])
            store.set_active_group(direction['id'])
            session = ProjectSession()
            session.open_project(root)
            changed: list[str] = []
            session.active_group_changed.connect(changed.append)

            session.store.delete_group(direction['id'])
            session.synchronize_active_group(direction['id'])

            self.assertEqual(changed, [''])
            self.assertIsNone(session.active_group_id)

    def test_close_project_clears_context_and_emits_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            store = ProjectStore.create(root, name='Demo')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Idle', parent_id=subject['id'])
            direction = store.create_group(group_type='direction', name='S', parent_id=animation['id'])
            store.set_active_group(direction['id'])
            session = ProjectSession()
            session.open_project(root)
            events: list[str] = []
            session.active_group_will_change.connect(lambda *_: events.append('will'))
            session.active_group_changed.connect(lambda value: events.append(f'group:{value}'))
            session.project_closed.connect(lambda: events.append('closed'))

            session.close_project()

            self.assertIsNone(session.store)
            self.assertIsNone(session.project_path)
            self.assertIsNone(session.active_group_id)
            self.assertEqual(events, ['will', 'group:', 'closed'])


if __name__ == '__main__':
    unittest.main()
