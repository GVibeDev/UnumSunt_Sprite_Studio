from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Callable, Mapping, Sequence

import numpy as np

from app.alignment_engine import (
    SubjectFrame,
    alpha_bounding_box,
    create_spritesheet,
    render_aligned_frame,
)
from app.export_service import save_rgba_image
from app.output_geometry import analyze_canvas_geometry
from app.models import (
    AlignmentSettings,
    ChromaKeySettings,
    FrameAlignmentState,
    VideoMetadata,
)


class AlignmentExportError(RuntimeError):
    """Raised when an aligned animation cannot be exported."""


LATERAL_MIRROR_MAP = {
    'north-east': 'north-west',
    'east': 'west',
    'south-east': 'south-west',
    'north-west': 'north-east',
    'west': 'east',
    'south-west': 'south-east',
    'ne': 'nw',
    'e': 'w',
    'se': 'sw',
    'nw': 'ne',
    'w': 'e',
    'sw': 'se',
}


def _safe_slug(value: str, fallback: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-_")
    return normalized or fallback


def _resolve_mirrored_direction(direction: str) -> str:
    normalized = direction.strip().lower()
    mirrored = LATERAL_MIRROR_MAP.get(normalized)
    if mirrored is None:
        raise AlignmentExportError(
            'Il mirror laterale è disponibile solo per NE/E/SE/NW/W/SW.'
        )
    return mirrored


def _build_frame_entries(
    *,
    frame_indices: Sequence[int],
    subjects: Mapping[int, SubjectFrame],
    states: Mapping[int, FrameAlignmentState],
    video_metadata: VideoMetadata,
    rendered_frames: Sequence[np.ndarray],
    placements: Sequence[object],
    alignment_settings: AlignmentSettings,
    extension: str,
    prefix: str,
    mirrored: bool,
    mirrored_from_direction: str | None,
) -> list[dict]:
    frame_entries: list[dict] = []
    for sequence_index, frame_index in enumerate(frame_indices):
        subject = subjects[frame_index]
        state = states[frame_index]
        rendered = rendered_frames[sequence_index]
        placement = placements[sequence_index]
        filename = f'{prefix}-frame-{sequence_index:03d}.{extension}'
        frame_entries.append(
            {
                'sequence_index': sequence_index,
                'source_frame_index': frame_index,
                'source_time_seconds': video_metadata.frame_time_seconds(frame_index),
                'file': filename,
                'source_crop_box': list(subject.crop_box),
                'source_size': [subject.width, subject.height],
                **state.to_dict(),
                **placement.to_dict(),
                'alpha_box_canvas': (
                    list(alpha_bounding_box(rendered))
                    if alpha_bounding_box(rendered) is not None
                    else None
                ),
                'duration_ms': round(1000.0 / alignment_settings.fps, 4),
                'mirrored': bool(mirrored),
                'mirrored_from_direction': mirrored_from_direction,
            }
        )
    return frame_entries


def _export_variant(
    *,
    rendered_frames: Sequence[np.ndarray],
    frame_indices: Sequence[int],
    subjects: Mapping[int, SubjectFrame],
    states: Mapping[int, FrameAlignmentState],
    placements: Sequence[object],
    video_metadata: VideoMetadata,
    chroma_settings: ChromaKeySettings,
    alignment_settings: AlignmentSettings,
    output_dir: Path,
    animation_name: str,
    direction: str,
    extension: str,
    sheet_layout: str,
    sheet_columns: int,
    sheet_padding: int,
    webp_quality: int,
    mirrored: bool,
    mirrored_from_direction: str | None,
) -> tuple[dict, Path]:
    name_slug = _safe_slug(animation_name, 'animation')
    direction_slug = _safe_slug(direction, 'direction')
    prefix = f'{name_slug}-{direction_slug}'

    for sequence_index, rendered in enumerate(rendered_frames):
        filename = f'{prefix}-frame-{sequence_index:03d}.{extension}'
        save_rgba_image(
            rendered,
            output_dir / filename,
            extension,
            webp_quality=webp_quality,
        )

    frame_entries = _build_frame_entries(
        frame_indices=frame_indices,
        subjects=subjects,
        states=states,
        video_metadata=video_metadata,
        rendered_frames=rendered_frames,
        placements=placements,
        alignment_settings=alignment_settings,
        extension=extension,
        prefix=prefix,
        mirrored=mirrored,
        mirrored_from_direction=mirrored_from_direction,
    )

    sheet, sheet_positions, columns, rows = create_spritesheet(
        rendered_frames,
        layout=sheet_layout,
        columns=sheet_columns,
        padding=sheet_padding,
    )
    sheet_filename = f'{prefix}-spritesheet.{extension}'
    save_rgba_image(
        sheet,
        output_dir / sheet_filename,
        extension,
        webp_quality=webp_quality,
    )

    manifest = {
        'schema': 'unum-sunt-sprite-studio-animation-v4',
        'application_version': 'R5c4a',
        'exported_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_video': {
            'path': str(video_metadata.path),
            'filename': video_metadata.path.name,
            'width': video_metadata.width,
            'height': video_metadata.height,
            'fps': video_metadata.fps,
            'frame_count': video_metadata.frame_count,
            'duration_seconds': video_metadata.duration_seconds,
        },
        'chroma_key': chroma_settings.to_dict(),
        'animation': {
            'name': animation_name.strip() or 'animation',
            'direction': direction.strip() or 'direction',
            'fps': alignment_settings.fps,
            'loop': alignment_settings.loop,
            'frame_count': len(rendered_frames),
            'mirrored': bool(mirrored),
            'mirrored_from_direction': mirrored_from_direction,
        },
        'canvas': alignment_settings.to_dict(),
        'geometry_diagnostics': analyze_canvas_geometry(subjects, states, alignment_settings).to_dict(),
        'sheet': {
            'file': sheet_filename,
            'layout': sheet_layout,
            'columns': columns,
            'rows': rows,
            'padding': int(sheet_padding),
            'width': int(sheet.shape[1]),
            'height': int(sheet.shape[0]),
            'frames': sheet_positions,
        },
        'frames': frame_entries,
    }

    manifest_path = output_dir / f'{prefix}-manifest.json'
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    return manifest, manifest_path


def export_aligned_animation(
    *,
    frame_indices: Sequence[int],
    subjects: Mapping[int, SubjectFrame],
    states: Mapping[int, FrameAlignmentState],
    video_metadata: VideoMetadata,
    chroma_settings: ChromaKeySettings,
    alignment_settings: AlignmentSettings,
    output_directory: str | Path,
    animation_name: str,
    direction: str,
    output_format: str = 'png',
    sheet_layout: str = 'horizontal',
    sheet_columns: int = 8,
    sheet_padding: int = 0,
    webp_quality: int = 95,
    mirror_mode: str = 'none',
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> dict:
    if not frame_indices:
        raise AlignmentExportError('Nessun fotogramma da esportare.')

    alignment_settings.validate()
    extension = output_format.lower().strip()
    if extension not in {'png', 'webp'}:
        raise AlignmentExportError(f'Formato non supportato: {output_format}')

    output_dir = Path(output_directory).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    variant_directions = [direction]
    mirrored_direction: str | None = None
    if mirror_mode == 'opposite-lateral':
        mirrored_direction = _resolve_mirrored_direction(direction)
        variant_directions.append(mirrored_direction)
    elif mirror_mode not in {'none', ''}:
        raise AlignmentExportError(f'Modalità mirror non supportata: {mirror_mode}')

    placements = []
    primary_rendered_frames: list[np.ndarray] = []
    total_steps = len(variant_directions) * (len(frame_indices) + 1)
    step_counter = 0

    for frame_index in frame_indices:
        subject = subjects.get(frame_index)
        state = states.get(frame_index)
        if subject is None or state is None:
            raise AlignmentExportError(
                f'Dati di allineamento mancanti per il frame {frame_index}.'
            )
        rendered, placement = render_aligned_frame(subject, state, alignment_settings)
        primary_rendered_frames.append(rendered)
        placements.append(placement)

    primary_manifest, primary_manifest_path = _export_variant(
        rendered_frames=primary_rendered_frames,
        frame_indices=frame_indices,
        subjects=subjects,
        states=states,
        placements=placements,
        video_metadata=video_metadata,
        chroma_settings=chroma_settings,
        alignment_settings=alignment_settings,
        output_dir=output_dir,
        animation_name=animation_name,
        direction=direction,
        extension=extension,
        sheet_layout=sheet_layout,
        sheet_columns=sheet_columns,
        sheet_padding=sheet_padding,
        webp_quality=webp_quality,
        mirrored=False,
        mirrored_from_direction=None,
    )
    # replay progress for primary files
    for frame_index in frame_indices:
        step_counter += 1
        if progress_callback is not None:
            progress_callback(step_counter, total_steps, frame_index)
    step_counter += 1
    if progress_callback is not None:
        progress_callback(step_counter, total_steps, -1)

    generated_exports = [
        {
            'direction': primary_manifest['animation']['direction'],
            'mirrored': False,
            'mirrored_from_direction': None,
            'manifest_file': primary_manifest_path.name,
            'sheet_file': primary_manifest['sheet']['file'],
        }
    ]

    if mirrored_direction is not None:
        mirrored_rendered_frames = [np.ascontiguousarray(np.flip(frame, axis=1)) for frame in primary_rendered_frames]
        mirrored_manifest, mirrored_manifest_path = _export_variant(
            rendered_frames=mirrored_rendered_frames,
            frame_indices=frame_indices,
            subjects=subjects,
            states=states,
            placements=placements,
            video_metadata=video_metadata,
            chroma_settings=chroma_settings,
            alignment_settings=alignment_settings,
            output_dir=output_dir,
            animation_name=animation_name,
            direction=mirrored_direction,
            extension=extension,
            sheet_layout=sheet_layout,
            sheet_columns=sheet_columns,
            sheet_padding=sheet_padding,
            webp_quality=webp_quality,
            mirrored=True,
            mirrored_from_direction=direction.strip() or 'direction',
        )
        for frame_index in frame_indices:
            step_counter += 1
            if progress_callback is not None:
                progress_callback(step_counter, total_steps, frame_index)
        step_counter += 1
        if progress_callback is not None:
            progress_callback(step_counter, total_steps, -1)
        primary_manifest['mirrored_export'] = {
            'direction': mirrored_manifest['animation']['direction'],
            'mirrored': True,
            'mirrored_from_direction': direction.strip() or 'direction',
            'manifest_file': mirrored_manifest_path.name,
            'sheet_file': mirrored_manifest['sheet']['file'],
        }
        generated_exports.append(primary_manifest['mirrored_export'])

    primary_manifest['generated_exports'] = generated_exports
    primary_manifest['export_options'] = {
        'format': extension,
        'sheet_layout': sheet_layout,
        'sheet_columns': int(sheet_columns),
        'sheet_padding': int(sheet_padding),
        'mirror_mode': mirror_mode or 'none',
    }
    primary_manifest_path.write_text(
        json.dumps(primary_manifest, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    return primary_manifest
