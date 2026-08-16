from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
from PIL import Image

from app.alignment_engine import create_spritesheet
from app.chroma_key import apply_chroma_key, crop_rgba_to_subject
from app.models import ChromaKeySettings, ExportSettings, VideoMetadata


class ExportError(RuntimeError):
    """Raised when one or more frames cannot be exported."""


def save_rgba_image(
    rgba: np.ndarray,
    output_path: str | Path,
    output_format: str,
    webp_quality: int = 95,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(rgba, mode="RGBA")
    fmt = output_format.lower()

    if fmt == "png":
        image.save(path, format="PNG", optimize=True)
    elif fmt == "webp":
        image.save(
            path,
            format="WEBP",
            lossless=True,
            quality=max(1, min(100, int(webp_quality))),
            method=6,
        )
    else:
        raise ExportError(f"Formato non supportato: {output_format}")

    return path


def apply_background_to_rgba(
    rgba: np.ndarray,
    *,
    mode: str = 'transparent',
    background_rgb: tuple[int, int, int] = (0, 0, 0),
) -> np.ndarray:
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ExportError('È richiesta un\'immagine RGBA.')
    mode_key = mode.lower().strip()
    if mode_key == 'transparent':
        return rgba.copy()
    if mode_key != 'solid':
        raise ExportError(f'Modalità sfondo non supportata: {mode}')
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    fg = rgba[:, :, :3].astype(np.float32)
    bg = np.zeros_like(fg) + np.array(background_rgb, dtype=np.float32)
    mixed = fg * alpha + bg * (1.0 - alpha)
    result = np.zeros_like(rgba)
    result[:, :, :3] = np.clip(mixed, 0, 255).astype(np.uint8)
    result[:, :, 3] = 255
    return result


def scale_rgba_nearest(rgba: np.ndarray, factor: int = 1) -> np.ndarray:
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ExportError('È richiesta un\'immagine RGBA.')
    factor = int(factor)
    if factor < 1 or factor > 16:
        raise ExportError('Il fattore di scala deve essere compreso tra 1 e 16.')
    if factor == 1:
        return rgba.copy()
    return np.repeat(np.repeat(rgba, factor, axis=0), factor, axis=1)


def export_rgba_bundle(
    *,
    rgba_frames: Sequence[np.ndarray],
    output_directory: str | Path,
    base_name: str,
    output_format: str = 'png',
    include_frames: bool = True,
    include_sheet: bool = True,
    sheet_layout: str = 'horizontal',
    sheet_columns: int = 8,
    sheet_padding: int = 0,
    scale_factor: int = 1,
    background_mode: str = 'transparent',
    background_rgb: tuple[int, int, int] = (0, 0, 0),
    webp_quality: int = 95,
    source_kind: str = 'aligned',
    metadata: dict | None = None,
) -> dict:
    if not rgba_frames:
        raise ExportError('Nessun frame RGBA da esportare.')
    normalized_frames = [np.asarray(frame).copy() for frame in rgba_frames]
    first_shape = normalized_frames[0].shape
    if len(first_shape) != 3 or first_shape[2] != 4:
        raise ExportError('I frame devono essere RGBA.')
    if any(frame.shape != first_shape for frame in normalized_frames):
        raise ExportError('Tutti i frame devono avere la stessa dimensione per l\'export finale.')
    output_dir = Path(output_directory).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = output_format.lower().strip()
    if ext not in {'png', 'webp'}:
        raise ExportError(f'Formato non supportato: {output_format}')
    processed_frames = [
        scale_rgba_nearest(apply_background_to_rgba(frame, mode=background_mode, background_rgb=background_rgb), factor=scale_factor)
        for frame in normalized_frames
    ]
    safe_name = ''.join(ch if ch.isalnum() or ch in '-_' else '-' for ch in base_name.strip().lower()).strip('-_') or 'animation'

    frame_entries: list[dict] = []
    if include_frames:
        for index, frame in enumerate(processed_frames):
            filename = f'{safe_name}-frame-{index:03d}.{ext}'
            save_rgba_image(frame, output_dir / filename, ext, webp_quality=webp_quality)
            frame_entries.append({'index': index, 'file': filename, 'width': int(frame.shape[1]), 'height': int(frame.shape[0])})

    sheet_info = None
    if include_sheet:
        sheet, positions, columns, rows = create_spritesheet(processed_frames, layout=sheet_layout, columns=sheet_columns, padding=sheet_padding)
        sheet_filename = f'{safe_name}-spritesheet.{ext}'
        save_rgba_image(sheet, output_dir / sheet_filename, ext, webp_quality=webp_quality)
        sheet_info = {
            'file': sheet_filename,
            'layout': sheet_layout,
            'columns': columns,
            'rows': rows,
            'padding': int(sheet_padding),
            'width': int(sheet.shape[1]),
            'height': int(sheet.shape[0]),
            'frames': positions,
        }

    manifest = {
        'schema': 'unum-sunt-sprite-studio-production-v1',
        'application_version': 'R5c4a',
        'exported_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_kind': source_kind,
        'base_name': safe_name,
        'output': {
            'format': ext,
            'include_frames': bool(include_frames),
            'include_sheet': bool(include_sheet),
            'sheet_layout': sheet_layout,
            'sheet_columns': int(sheet_columns),
            'sheet_padding': int(sheet_padding),
            'scale_factor': int(scale_factor),
            'background_mode': background_mode,
            'background_rgb': list(background_rgb),
            'webp_quality': int(webp_quality),
        },
        'frame_count': len(processed_frames),
        'frame_size': [int(processed_frames[0].shape[1]), int(processed_frames[0].shape[0])],
        'frames': frame_entries,
        'sheet': sheet_info,
        'metadata': metadata or {},
    }
    manifest_path = output_dir / f'{safe_name}-production-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


def export_selected_frames(
    *,
    frame_indices: Iterable[int],
    frame_loader: Callable[[int], np.ndarray],
    video_metadata: VideoMetadata,
    chroma_settings: ChromaKeySettings,
    export_settings: ExportSettings,
    output_directory: str | Path,
    progress_callback: Callable[[int, int, int], None] | None = None,
    rgba_override_provider: Callable[[int], np.ndarray | None] | None = None,
) -> dict:
    indices = sorted(set(int(index) for index in frame_indices))
    if not indices:
        raise ExportError("Nessun fotogramma selezionato.")

    output_dir = Path(output_directory).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    extension = export_settings.normalized_format()
    exported = []
    total = len(indices)

    for position, frame_index in enumerate(indices, start=1):
        if frame_index < 0 or frame_index >= video_metadata.frame_count:
            raise ExportError(f"Indice fotogramma fuori intervallo: {frame_index}")

        override = rgba_override_provider(frame_index) if rgba_override_provider is not None else None
        if override is not None:
            rgba = override.copy()
        else:
            source_rgb = frame_loader(frame_index)
            rgba, _ = apply_chroma_key(source_rgb, chroma_settings)
        crop_box = None

        if export_settings.crop_to_subject:
            rgba, crop_box = crop_rgba_to_subject(
                rgba,
                padding=export_settings.padding,
            )

        filename = f"frame-{frame_index:06d}.{extension}"
        output_path = output_dir / filename
        save_rgba_image(
            rgba,
            output_path,
            extension,
            webp_quality=export_settings.webp_quality,
        )

        exported.append(
            {
                "frame_index": frame_index,
                "time_seconds": video_metadata.frame_time_seconds(frame_index),
                "file": filename,
                "width": int(rgba.shape[1]),
                "height": int(rgba.shape[0]),
                "crop_box_source": list(crop_box) if crop_box else None,
            }
        )

        if progress_callback is not None:
            progress_callback(position, total, frame_index)

    manifest = {
        "schema": "unum-sunt-sprite-studio-export-v1",
        "application_version": "R5c3",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_video": {
            "path": str(video_metadata.path),
            "filename": video_metadata.path.name,
            "width": video_metadata.width,
            "height": video_metadata.height,
            "fps": video_metadata.fps,
            "frame_count": video_metadata.frame_count,
            "duration_seconds": video_metadata.duration_seconds,
        },
        "chroma_key": chroma_settings.to_dict(),
        "export": {
            "format": extension,
            "crop_to_subject": export_settings.crop_to_subject,
            "padding": export_settings.padding,
            "webp_quality": export_settings.webp_quality,
        },
        "frames": exported,
    }

    manifest_path = output_dir / "export-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest
