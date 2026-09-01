from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.project_state import ProjectContext, ProjectState, SourceRef
from app.project_store import ProjectStore


class ProjectSession(QObject):
    """Runtime project/session boundary for the workstation.

    ``ProjectStore`` remains the persistence layer.  ProjectSession owns the
    currently adopted store and the active Project Group identity so other
    workspaces no longer need to reach through ``ProjectWorkspace`` to discover
    project context.

    Phase 2A adds a small ``ProjectState`` for transient production identity,
    but deliberately does not cache a second copy of the project document: the
    active ``ProjectStore`` remains the single authoritative persistence object.
    """

    project_changed = Signal(str)
    project_closed = Signal()
    active_group_will_change = Signal(str, str)
    active_group_changed = Signal(str)
    project_state_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store: ProjectStore | None = None
        self._project_state = ProjectState()

    @property
    def store(self) -> ProjectStore | None:
        return self._store

    @property
    def project_state(self) -> ProjectState:
        return self._project_state

    @property
    def project_context(self) -> ProjectContext:
        lineage: list[dict] = []
        if self._store is not None and self.active_group_id:
            try:
                lineage = self._store.group_lineage(self.active_group_id)
            except (KeyError, ValueError):
                lineage = []
        return self._project_state.context_from_lineage(lineage)

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
        self._project_state.adopt_project(current, self.active_group_id)
        self.project_state_changed.emit()
        if current is not None:
            self.project_changed.emit(current)
        return self._store

    def open_project(self, project_dir_or_file: str | Path) -> ProjectStore:
        self._store = ProjectStore.open(Path(project_dir_or_file))
        current = self.project_path
        self._project_state.adopt_project(current, self.active_group_id)
        self.project_state_changed.emit()
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
        self._project_state.clear_project()
        self.project_state_changed.emit()
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
        self._project_state.set_active_group(group_id)
        self.project_state_changed.emit()
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
            self._project_state.set_active_group(current or None)
            self.project_state_changed.emit()
            self.active_group_changed.emit(current)

    def set_current_asset(self, asset_id: str | None) -> None:
        before = self._project_state.context_revision
        self._project_state.set_current_asset(asset_id)
        if self._project_state.context_revision != before:
            self.project_state_changed.emit()

    def set_current_source(
        self,
        *,
        kind: str,
        path: str,
        manifest_path: str | None = None,
    ) -> None:
        before = self._project_state.context_revision
        self._project_state.set_current_source(
            SourceRef(kind=kind, path=path, manifest_path=manifest_path)
        )
        if self._project_state.context_revision != before:
            self.project_state_changed.emit()

    def clear_current_source(self) -> None:
        before = self._project_state.context_revision
        self._project_state.set_current_source(None)
        if self._project_state.context_revision != before:
            self.project_state_changed.emit()

    def set_current_frame(self, frame_index: int | None) -> None:
        before = self._project_state.context_revision
        self._project_state.set_current_frame(frame_index)
        if self._project_state.context_revision != before:
            self.project_state_changed.emit()

    def set_selected_frames(self, frame_indices: Iterable[int]) -> None:
        before = self._project_state.context_revision
        self._project_state.set_selected_frames(frame_indices)
        if self._project_state.context_revision != before:
            self.project_state_changed.emit()

    def clear_production_context(self) -> None:
        before = self._project_state.context_revision
        self._project_state.clear_production_context()
        if self._project_state.context_revision != before:
            self.project_state_changed.emit()
