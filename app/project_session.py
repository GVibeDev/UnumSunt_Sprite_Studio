from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.project_store import ProjectStore


class ProjectSession(QObject):
    """Runtime project/session boundary for the workstation.

    ``ProjectStore`` remains the persistence layer.  ProjectSession owns the
    currently adopted store and the active Project Group identity so other
    workspaces no longer need to reach through ``ProjectWorkspace`` to discover
    project context.

    Phase 1E deliberately does not cache a second copy of the project document:
    the active ``ProjectStore`` remains the single authoritative persistence
    object.
    """

    project_changed = Signal(str)
    project_closed = Signal()
    active_group_will_change = Signal(str, str)
    active_group_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store: ProjectStore | None = None

    @property
    def store(self) -> ProjectStore | None:
        return self._store

    @property
    def project_path(self) -> str | None:
        if self._store is None or self._store.path is None:
            return None
        return str(self._store.path.parent)

    @property
    def active_group_id(self) -> str | None:
        if self._store is None:
            return None
        group = self._store.get_active_group()
        return str(group['id']) if group else None

    def create_project(self, project_dir: str | Path, *, name: str | None = None) -> ProjectStore:
        self._store = ProjectStore.create(Path(project_dir), name=name)
        current = self.project_path
        if current is not None:
            self.project_changed.emit(current)
        return self._store

    def open_project(self, project_dir_or_file: str | Path) -> ProjectStore:
        self._store = ProjectStore.open(Path(project_dir_or_file))
        current = self.project_path
        if current is not None:
            self.project_changed.emit(current)
        active = self.active_group_id
        if active:
            self.active_group_changed.emit(active)
        return self._store

    def close_project(self) -> None:
        if self._store is None:
            return
        old_active = self.active_group_id or ''
        if old_active:
            self.active_group_will_change.emit(old_active, '')
        self._store = None
        if old_active:
            self.active_group_changed.emit('')
        self.project_closed.emit()

    def set_active_group(self, group_id: str | None) -> None:
        if self._store is None:
            raise RuntimeError('No project is open.')
        target = '' if group_id is None else str(group_id)
        old = self.active_group_id or ''
        if old == target:
            return
        # Validate before announcing a transition: listeners may snapshot or
        # quiesce expensive UI state on ``active_group_will_change``.
        if group_id is not None:
            group = self._store.get_group(target)
            if group is None:
                raise KeyError(f'Project group not found: {target}')
            if group.get('type') != 'direction':
                raise ValueError('Only a direction group can become the active production context.')
        self.active_group_will_change.emit(old, target)
        self._store.set_active_group(group_id)
        self.active_group_changed.emit(target)

    def refresh_active_group(self) -> None:
        """Re-emit the current context after external group data changed."""
        self.active_group_changed.emit(self.active_group_id or '')

    def synchronize_active_group(self, previous_group_id: str | None) -> None:
        """Publish a context change caused by a direct ProjectStore mutation.

        This is a transition helper for Phase 1E while ProjectWorkspace still
        owns group CRUD UI.  It prevents ProjectSession from silently diverging
        when a store operation (for example deleting the active group) changes
        ``active_group_id`` without going through ``set_active_group``.
        """
        previous = str(previous_group_id or '')
        current = self.active_group_id or ''
        if current != previous:
            self.active_group_changed.emit(current)
