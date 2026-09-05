from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class SourceRef:
    """Lightweight reference to the source currently loaded by CREATE.

    This object deliberately stores identity only. Pixel buffers, decoded frames,
    manifests and persisted project payloads continue to live in their existing
    owners. ProjectState must never become a second project document cache.
    """

    kind: str
    path: str
    manifest_path: str | None = None

    def __post_init__(self) -> None:
        kind = str(self.kind).strip()
        path = str(self.path).strip()
        if not kind:
            raise ValueError('Source kind cannot be empty.')
        if not path:
            raise ValueError('Source path cannot be empty.')
        object.__setattr__(self, 'kind', kind)
        object.__setattr__(self, 'path', path)
        if self.manifest_path is not None:
            manifest = str(self.manifest_path).strip()
            object.__setattr__(self, 'manifest_path', manifest or None)


@dataclass(frozen=True, slots=True)
class ProjectContext:
    """Read-only orientation data for the future CREATE project breadcrumb."""

    project_path: str | None = None
    subject_id: str | None = None
    subject_name: str | None = None
    animation_id: str | None = None
    animation_name: str | None = None
    direction_id: str | None = None
    direction_name: str | None = None
    asset_id: str | None = None
    source_kind: str | None = None
    source_name: str | None = None
    frame_index: int | None = None

    @property
    def breadcrumb_labels(self) -> tuple[str, ...]:
        labels = [self.subject_name, self.animation_name, self.direction_name]
        return tuple(value for value in labels if value)


@dataclass(slots=True)
class ProjectState:
    """Transient production state scoped by ProjectSession.

    ProjectStore remains the sole persisted project authority.  This class owns
    only runtime identity/navigation state needed by the shared CREATE workspace.
    It intentionally does not contain project JSON, decoded image data or a copy
    of ProjectStore group payloads.
    """

    project_path: str | None = None
    active_group_id: str | None = None
    current_asset_id: str | None = None
    current_source: SourceRef | None = None
    current_frame_index: int | None = None
    selected_frames: tuple[int, ...] = ()
    context_revision: int = 0

    def _touch(self) -> None:
        self.context_revision += 1

    def _clear_production_fields(self) -> None:
        self.current_asset_id = None
        self.current_source = None
        self.current_frame_index = None
        self.selected_frames = ()

    def adopt_project(self, project_path: str | None, active_group_id: str | None = None) -> None:
        normalized_path = str(project_path).strip() if project_path else None
        normalized_group = str(active_group_id).strip() if active_group_id else None
        self.project_path = normalized_path
        self.active_group_id = normalized_group
        # Adopting a ProjectStore is a lifecycle boundary even when the same
        # path is reopened. Never carry source/frame state across store adoption.
        self._clear_production_fields()
        self._touch()

    def clear_project(self) -> None:
        if (
            self.project_path is None
            and self.active_group_id is None
            and self.current_asset_id is None
            and self.current_source is None
            and self.current_frame_index is None
            and not self.selected_frames
        ):
            return
        self.project_path = None
        self.active_group_id = None
        self._clear_production_fields()
        self._touch()

    def set_active_group(self, group_id: str | None) -> None:
        normalized = str(group_id).strip() if group_id else None
        if self.active_group_id == normalized:
            return
        self.active_group_id = normalized
        self._clear_production_fields()
        self._touch()

    def clear_production_context(self) -> None:
        if (
            self.current_asset_id is None
            and self.current_source is None
            and self.current_frame_index is None
            and not self.selected_frames
        ):
            return
        self._clear_production_fields()
        self._touch()

    def set_current_asset(self, asset_id: str | None) -> None:
        normalized = str(asset_id).strip() if asset_id else None
        if self.current_asset_id == normalized:
            return
        self.current_asset_id = normalized
        self._touch()

    def set_current_source(self, source: SourceRef | None) -> None:
        if self.current_source == source:
            return
        self.current_source = source
        # Frame identity belongs to a source. Never keep a selection from a
        # previous source after the source reference changes.
        self.current_frame_index = None
        self.selected_frames = ()
        self._touch()

    def set_current_frame(self, frame_index: int | None) -> None:
        normalized = None if frame_index is None else int(frame_index)
        if normalized is not None and normalized < 0:
            raise ValueError('Frame index cannot be negative.')
        if self.current_frame_index == normalized:
            return
        self.current_frame_index = normalized
        self._touch()

    def set_selected_frames(self, frame_indices: Iterable[int]) -> None:
        normalized = tuple(sorted({int(value) for value in frame_indices}))
        if any(value < 0 for value in normalized):
            raise ValueError('Selected frame indices cannot be negative.')
        if self.selected_frames == normalized:
            return
        self.selected_frames = normalized
        self._touch()

    def context_from_lineage(self, lineage: Sequence[dict]) -> ProjectContext:
        by_type = {
            str(group.get('type')): group
            for group in lineage
            if isinstance(group, dict) and group.get('type')
        }
        subject = by_type.get('subject', {})
        animation = by_type.get('animation', {})
        direction = by_type.get('direction', {})
        source = self.current_source
        return ProjectContext(
            project_path=self.project_path,
            subject_id=str(subject.get('id')) if subject.get('id') else None,
            subject_name=str(subject.get('name')) if subject.get('name') else None,
            animation_id=str(animation.get('id')) if animation.get('id') else None,
            animation_name=str(animation.get('name')) if animation.get('name') else None,
            direction_id=str(direction.get('id')) if direction.get('id') else None,
            direction_name=str(direction.get('name')) if direction.get('name') else None,
            asset_id=self.current_asset_id,
            source_kind=source.kind if source is not None else None,
            source_name=Path(source.path).name if source is not None else None,
            frame_index=self.current_frame_index,
        )

    def diagnostic_snapshot(self) -> dict:
        """Serializable diagnostics only; never written as project persistence."""
        return {
            'project_path': self.project_path,
            'active_group_id': self.active_group_id,
            'current_asset_id': self.current_asset_id,
            'current_source': (
                {
                    'kind': self.current_source.kind,
                    'path': self.current_source.path,
                    'manifest_path': self.current_source.manifest_path,
                }
                if self.current_source is not None
                else None
            ),
            'current_frame_index': self.current_frame_index,
            'selected_frames': list(self.selected_frames),
            'context_revision': self.context_revision,
        }
