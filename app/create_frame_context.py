from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


ONION_SKIN_MODES = ('off', 'previous', 'next')


def normalize_onion_skin_mode(value: str | None) -> str:
    normalized = str(value or 'off').strip().lower()
    if normalized not in ONION_SKIN_MODES:
        raise ValueError(f'Unsupported onion-skin mode: {value}')
    return normalized


@dataclass(frozen=True, slots=True)
class CreateFrameContext:
    """Presentation snapshot for the active decoded CREATE source.

    The object does not own decoded pixels and is never written to ProjectStore.
    Current/selected frame identity remains mirrored in ProjectState while source
    geometry/timing remains owned by VideoSource.  This snapshot simply gives the
    persistent CREATE frame strip one coherent, immutable view of that runtime
    context.
    """

    frame_count: int = 0
    current_frame_index: int | None = None
    selected_frames: tuple[int, ...] = ()
    fps: float | None = None
    source_kind: str | None = None
    source_label: str | None = None

    def __post_init__(self) -> None:
        count = int(self.frame_count)
        if count < 0:
            raise ValueError('Frame count cannot be negative.')
        object.__setattr__(self, 'frame_count', count)

        fps = None if self.fps is None else float(self.fps)
        if fps is not None and fps <= 0:
            raise ValueError('Frame FPS must be greater than zero when provided.')
        object.__setattr__(self, 'fps', fps)

        current = None if self.current_frame_index is None else int(self.current_frame_index)
        if count == 0:
            if current is not None:
                raise ValueError('An empty frame source cannot have a current frame.')
        elif current is not None and not 0 <= current < count:
            raise ValueError('Current frame index is outside the source range.')
        object.__setattr__(self, 'current_frame_index', current)

        normalized_selection = tuple(sorted({int(value) for value in self.selected_frames}))
        if any(value < 0 or value >= count for value in normalized_selection):
            raise ValueError('Selected frame index is outside the source range.')
        object.__setattr__(self, 'selected_frames', normalized_selection)

        source_kind = str(self.source_kind).strip() if self.source_kind else None
        source_label = str(self.source_label).strip() if self.source_label else None
        object.__setattr__(self, 'source_kind', source_kind or None)
        object.__setattr__(self, 'source_label', source_label or None)

    @property
    def has_frames(self) -> bool:
        return self.frame_count > 0

    @property
    def selection_count(self) -> int:
        return len(self.selected_frames)

    def frame_time_seconds(self, frame_index: int | None = None) -> float | None:
        if self.fps is None:
            return None
        target = self.current_frame_index if frame_index is None else int(frame_index)
        if target is None:
            return None
        if not 0 <= target < self.frame_count:
            raise ValueError('Frame index is outside the source range.')
        return float(target) / self.fps

    def onion_target_index(self, mode: str | None) -> int | None:
        normalized = normalize_onion_skin_mode(mode)
        current = self.current_frame_index
        if normalized == 'off' or current is None or self.frame_count <= 1:
            return None
        if normalized == 'previous':
            return current - 1 if current > 0 else None
        return current + 1 if current + 1 < self.frame_count else None

    def with_selected_frames(self, frame_indices: Iterable[int]) -> 'CreateFrameContext':
        return CreateFrameContext(
            frame_count=self.frame_count,
            current_frame_index=self.current_frame_index,
            selected_frames=tuple(frame_indices),
            fps=self.fps,
            source_kind=self.source_kind,
            source_label=self.source_label,
        )
