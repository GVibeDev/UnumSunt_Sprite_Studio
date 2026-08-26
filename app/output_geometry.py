from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.alignment_engine import SubjectFrame
from app.models import AlignmentSettings, FrameAlignmentState


MIN_OUTPUT_DIMENSION = 36
MAX_OUTPUT_DIMENSION = 256


@dataclass(frozen=True)
class OutputSizePreset:
    key: str
    label: str
    width: int | None
    height: int | None
    category: str

    @property
    def is_custom(self) -> bool:
        return self.width is None or self.height is None


OUTPUT_SIZE_PRESETS: tuple[OutputSizePreset, ...] = (
    OutputSizePreset('custom', 'Custom', None, None, 'custom'),
    OutputSizePreset('square-36', 'Square · 36 × 36', 36, 36, 'square'),
    OutputSizePreset('square-48', 'Square · 48 × 48', 48, 48, 'square'),
    OutputSizePreset('square-64', 'Square · 64 × 64', 64, 64, 'square'),
    OutputSizePreset('square-80', 'Square · 80 × 80', 80, 80, 'square'),
    OutputSizePreset('square-96', 'Square · 96 × 96', 96, 96, 'square'),
    OutputSizePreset('square-128', 'Square · 128 × 128', 128, 128, 'square'),
    OutputSizePreset('square-160', 'Square · 160 × 160', 160, 160, 'square'),
    OutputSizePreset('square-192', 'Square · 192 × 192', 192, 192, 'square'),
    OutputSizePreset('square-224', 'Square · 224 × 224', 224, 224, 'square'),
    OutputSizePreset('square-256', 'Square · 256 × 256', 256, 256, 'square'),
    OutputSizePreset('portrait-48x64', 'Vertical · 48 × 64', 48, 64, 'portrait'),
    OutputSizePreset('portrait-64x96', 'Vertical · 64 × 96', 64, 96, 'portrait'),
    OutputSizePreset('portrait-80x112', 'Vertical · 80 × 112', 80, 112, 'portrait'),
    OutputSizePreset('portrait-96x128', 'Vertical · 96 × 128', 96, 128, 'portrait'),
    OutputSizePreset('portrait-128x192', 'Vertical · 128 × 192', 128, 192, 'portrait'),
    OutputSizePreset('portrait-160x224', 'Vertical · 160 × 224', 160, 224, 'portrait'),
    OutputSizePreset('portrait-192x256', 'Vertical · 192 × 256', 192, 256, 'portrait'),
    OutputSizePreset('landscape-64x48', 'Horizontal · 64 × 48', 64, 48, 'landscape'),
    OutputSizePreset('landscape-96x64', 'Horizontal · 96 × 64', 96, 64, 'landscape'),
    OutputSizePreset('landscape-112x80', 'Horizontal · 112 × 80', 112, 80, 'landscape'),
    OutputSizePreset('landscape-128x96', 'Horizontal · 128 × 96', 128, 96, 'landscape'),
    OutputSizePreset('landscape-192x128', 'Horizontal · 192 × 128', 192, 128, 'landscape'),
    OutputSizePreset('landscape-224x160', 'Horizontal · 224 × 160', 224, 160, 'landscape'),
    OutputSizePreset('landscape-256x192', 'Horizontal · 256 × 192', 256, 192, 'landscape'),
)


@dataclass(frozen=True)
class CanvasGeometryReport:
    width: int
    height: int
    total_frames: int
    clipped_frames: tuple[int, ...]
    margin_warning_frames: tuple[int, ...]
    maximum_overflow: tuple[int, int, int, int]

    @property
    def is_safe(self) -> bool:
        return not self.clipped_frames

    @property
    def shape(self) -> str:
        return classify_output_shape(self.width, self.height)

    def to_dict(self) -> dict:
        return {
            'size': [self.width, self.height],
            'shape': self.shape,
            'aspect_ratio': round(self.width / self.height, 8),
            'total_frames': self.total_frames,
            'clipped_frame_count': len(self.clipped_frames),
            'clipped_frames': list(self.clipped_frames),
            'margin_warning_frame_count': len(self.margin_warning_frames),
            'margin_warning_frames': list(self.margin_warning_frames),
            'maximum_overflow': {
                'left': self.maximum_overflow[0],
                'top': self.maximum_overflow[1],
                'right': self.maximum_overflow[2],
                'bottom': self.maximum_overflow[3],
            },
        }


def validate_output_size(width: int, height: int) -> tuple[int, int]:
    width = int(width)
    height = int(height)
    if not MIN_OUTPUT_DIMENSION <= width <= MAX_OUTPUT_DIMENSION:
        raise ValueError(
            f'Output width must be between {MIN_OUTPUT_DIMENSION} and {MAX_OUTPUT_DIMENSION} px.'
        )
    if not MIN_OUTPUT_DIMENSION <= height <= MAX_OUTPUT_DIMENSION:
        raise ValueError(
            f'Output height must be between {MIN_OUTPUT_DIMENSION} and {MAX_OUTPUT_DIMENSION} px.'
        )
    return width, height


def classify_output_shape(width: int, height: int) -> str:
    width, height = validate_output_size(width, height)
    if width == height:
        return 'square'
    return 'landscape' if width > height else 'portrait'


def preset_by_key(key: str) -> OutputSizePreset:
    for preset in OUTPUT_SIZE_PRESETS:
        if preset.key == key:
            return preset
    return OUTPUT_SIZE_PRESETS[0]


def preset_for_size(width: int, height: int) -> OutputSizePreset:
    width, height = validate_output_size(width, height)
    for preset in OUTPUT_SIZE_PRESETS:
        if preset.width == width and preset.height == height:
            return preset
    return OUTPUT_SIZE_PRESETS[0]


def migrate_canvas_pivot(
    old_width: int,
    old_height: int,
    new_width: int,
    new_height: int,
    pivot_x: float,
    pivot_y: float,
    *,
    proportional: bool,
) -> tuple[float, float]:
    old_width = max(1, int(old_width))
    old_height = max(1, int(old_height))
    new_width, new_height = validate_output_size(new_width, new_height)
    if proportional:
        new_x = float(pivot_x) * new_width / old_width
        new_y = float(pivot_y) * new_height / old_height
    else:
        new_x = float(pivot_x)
        new_y = float(pivot_y)
    return (
        max(0.0, min(float(new_width), new_x)),
        max(0.0, min(float(new_height), new_y)),
    )


def locked_size_from_width(width: int, aspect_ratio: float) -> tuple[int, int]:
    if aspect_ratio <= 0:
        raise ValueError('The ratio must be positive.')
    width = max(MIN_OUTPUT_DIMENSION, min(MAX_OUTPUT_DIMENSION, int(width)))
    height = int(round(width / aspect_ratio))
    if height < MIN_OUTPUT_DIMENSION:
        height = MIN_OUTPUT_DIMENSION
        width = int(round(height * aspect_ratio))
    elif height > MAX_OUTPUT_DIMENSION:
        height = MAX_OUTPUT_DIMENSION
        width = int(round(height * aspect_ratio))
    return validate_output_size(width, height)


def locked_size_from_height(height: int, aspect_ratio: float) -> tuple[int, int]:
    if aspect_ratio <= 0:
        raise ValueError('The ratio must be positive.')
    height = max(MIN_OUTPUT_DIMENSION, min(MAX_OUTPUT_DIMENSION, int(height)))
    width = int(round(height * aspect_ratio))
    if width < MIN_OUTPUT_DIMENSION:
        width = MIN_OUTPUT_DIMENSION
        height = int(round(width / aspect_ratio))
    elif width > MAX_OUTPUT_DIMENSION:
        width = MAX_OUTPUT_DIMENSION
        height = int(round(width / aspect_ratio))
    return validate_output_size(width, height)


def analyze_canvas_geometry(
    subjects: Mapping[int, SubjectFrame],
    states: Mapping[int, FrameAlignmentState],
    settings: AlignmentSettings,
) -> CanvasGeometryReport:
    width, height = validate_output_size(settings.canvas_width, settings.canvas_height)
    clipped: list[int] = []
    margin_warnings: list[int] = []
    maximum = [0, 0, 0, 0]
    margin = max(0, int(settings.margin))

    for frame_index, subject in subjects.items():
        state = states.get(frame_index)
        if state is None:
            continue
        scaled_width = max(1, int(round(subject.width * settings.shared_scale)))
        scaled_height = max(1, int(round(subject.height * settings.shared_scale)))
        left = int(round(settings.canvas_pivot_x + state.offset_x - state.source_pivot_x * settings.shared_scale))
        top = int(round(settings.canvas_pivot_y + state.offset_y - state.source_pivot_y * settings.shared_scale))
        right = left + scaled_width
        bottom = top + scaled_height
        overflow = (
            max(0, -left),
            max(0, -top),
            max(0, right - width),
            max(0, bottom - height),
        )
        maximum = [max(maximum[i], overflow[i]) for i in range(4)]
        if any(overflow):
            clipped.append(int(frame_index))
        if left < margin or top < margin or right > width - margin or bottom > height - margin:
            margin_warnings.append(int(frame_index))

    return CanvasGeometryReport(
        width=width,
        height=height,
        total_frames=len(subjects),
        clipped_frames=tuple(sorted(clipped)),
        margin_warning_frames=tuple(sorted(set(margin_warnings))),
        maximum_overflow=tuple(maximum),
    )
