from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Sequence
import json

import cv2
import numpy as np

from app.performance_probe import perf_instrument


@dataclass(frozen=True)
class GridSliceSettings:
    frame_width: int
    frame_height: int
    rows: int
    columns: int
    horizontal_padding: int = 0
    vertical_padding: int = 0
    outer_margin: int = 0
    reading_order: str = 'row_major'

    def normalized(self) -> 'GridSliceSettings':
        order = str(self.reading_order).strip().lower()
        if order not in {'row_major', 'column_major'}:
            raise ValueError(f'Ordine lettura non supportato: {self.reading_order}')
        values = {
            'frame_width': int(self.frame_width),
            'frame_height': int(self.frame_height),
            'rows': int(self.rows),
            'columns': int(self.columns),
            'horizontal_padding': int(self.horizontal_padding),
            'vertical_padding': int(self.vertical_padding),
            'outer_margin': int(self.outer_margin),
        }
        if values['frame_width'] <= 0 or values['frame_height'] <= 0:
            raise ValueError('Frame width/height devono essere positivi.')
        if values['rows'] <= 0 or values['columns'] <= 0:
            raise ValueError('Rows/columns devono essere positivi.')
        if values['horizontal_padding'] < 0 or values['vertical_padding'] < 0 or values['outer_margin'] < 0:
            raise ValueError('Padding e margin non possono essere negativi.')
        return GridSliceSettings(reading_order=order, **values)

    def to_dict(self) -> dict:
        return asdict(self.normalized())


@dataclass(frozen=True)
class GridDetectionResult:
    settings: GridSliceSettings
    confidence: str
    reason: str


@dataclass(frozen=True)
class AtlasRegion:
    x: int
    y: int
    width: int
    height: int
    area: int

    def to_dict(self) -> dict:
        return asdict(self)


def ensure_rgba(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] not in (3, 4) or arr.dtype != np.uint8:
        raise ValueError('È richiesta un\'immagine RGB/RGBA uint8.')
    if arr.shape[2] == 4:
        return arr.copy()
    alpha = np.full(arr.shape[:2] + (1,), 255, dtype=np.uint8)
    return np.concatenate([arr, alpha], axis=2)


def load_image_rgba(path: str | Path) -> np.ndarray:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f'Spritesheet non trovato: {source}')
    raw = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise ValueError(f'Impossibile leggere lo spritesheet: {source}')
    if raw.ndim == 2:
        rgb = cv2.cvtColor(raw, cv2.COLOR_GRAY2RGB)
        return ensure_rgba(rgb)
    if raw.shape[2] == 4:
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2RGBA)
    if raw.shape[2] == 3:
        return ensure_rgba(cv2.cvtColor(raw, cv2.COLOR_BGR2RGB))
    raise ValueError('Formato immagine non supportato.')


def _intervals_from_boolean(values: np.ndarray) -> list[tuple[int, int]]:
    values = np.asarray(values, dtype=bool).reshape(-1)
    intervals: list[tuple[int, int]] = []
    start: int | None = None
    for index, active in enumerate(values.tolist()):
        if active and start is None:
            start = index
        elif not active and start is not None:
            intervals.append((start, index))
            start = None
    if start is not None:
        intervals.append((start, len(values)))
    return intervals


def _regular(values: Sequence[int], tolerance: int = 1) -> bool:
    if not values:
        return False
    return max(values) - min(values) <= max(0, int(tolerance))


def _derive_padding(intervals: list[tuple[int, int]]) -> int:
    if len(intervals) <= 1:
        return 0
    gaps = [intervals[i + 1][0] - intervals[i][1] for i in range(len(intervals) - 1)]
    if not _regular(gaps, tolerance=1):
        return 0
    return int(round(sum(gaps) / len(gaps)))


@perf_instrument('spritesheet.auto_detect_regular_grid')
def auto_detect_regular_grid(image_rgba: np.ndarray) -> GridDetectionResult:
    """Conservative regular-grid detection.

    First uses transparency. If the image is fully opaque, it searches for rows/columns
    that are almost uniform and border-colour-like, treating them as separators.
    The returned settings are always intended to be editable by the user.
    """
    rgba = ensure_rgba(image_rgba)
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3]

    if np.any(alpha < 250):
        occupied = alpha > 8
        x_intervals = _intervals_from_boolean(np.any(occupied, axis=0))
        y_intervals = _intervals_from_boolean(np.any(occupied, axis=1))
        widths = [b - a for a, b in x_intervals]
        heights = [b - a for a, b in y_intervals]
        if x_intervals and y_intervals and _regular(widths, 1) and _regular(heights, 1):
            hpad = _derive_padding(x_intervals)
            vpad = _derive_padding(y_intervals)
            left_margin = x_intervals[0][0]
            top_margin = y_intervals[0][0]
            right_margin = w - x_intervals[-1][1]
            bottom_margin = h - y_intervals[-1][1]
            margins = [left_margin, top_margin, right_margin, bottom_margin]
            margin = int(round(sum(margins) / 4)) if _regular(margins, 1) else min(margins)
            settings = GridSliceSettings(
                frame_width=int(round(sum(widths) / len(widths))),
                frame_height=int(round(sum(heights) / len(heights))),
                rows=len(y_intervals),
                columns=len(x_intervals),
                horizontal_padding=hpad,
                vertical_padding=vpad,
                outer_margin=max(0, margin),
            )
            expected_w = settings.outer_margin * 2 + settings.columns * settings.frame_width + (settings.columns - 1) * settings.horizontal_padding
            expected_h = settings.outer_margin * 2 + settings.rows * settings.frame_height + (settings.rows - 1) * settings.vertical_padding
            confidence = 'high' if abs(expected_w - w) <= 2 and abs(expected_h - h) <= 2 else 'medium'
            return GridDetectionResult(settings, confidence, 'Griglia rilevata dalla trasparenza e dagli intervalli occupati.')

    # Opaque fallback: separator lines similar to the border colour.
    rgb = rgba[:, :, :3].astype(np.int16)
    border_samples = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]], axis=0)
    border_color = np.median(border_samples, axis=0)
    column_mean = rgb.mean(axis=0)
    row_mean = rgb.mean(axis=1)
    column_std = rgb.std(axis=0).mean(axis=1)
    row_std = rgb.std(axis=1).mean(axis=1)
    col_distance = np.linalg.norm(column_mean - border_color[None, :], axis=1)
    row_distance = np.linalg.norm(row_mean - border_color[None, :], axis=1)
    separator_cols = (column_std < 3.0) & (col_distance < 8.0)
    separator_rows = (row_std < 3.0) & (row_distance < 8.0)
    content_cols = ~separator_cols
    content_rows = ~separator_rows
    x_intervals = [iv for iv in _intervals_from_boolean(content_cols) if iv[1] - iv[0] >= 2]
    y_intervals = [iv for iv in _intervals_from_boolean(content_rows) if iv[1] - iv[0] >= 2]
    widths = [b - a for a, b in x_intervals]
    heights = [b - a for a, b in y_intervals]
    if x_intervals and y_intervals and _regular(widths, 2) and _regular(heights, 2):
        settings = GridSliceSettings(
            frame_width=int(round(sum(widths) / len(widths))),
            frame_height=int(round(sum(heights) / len(heights))),
            rows=len(y_intervals),
            columns=len(x_intervals),
            horizontal_padding=_derive_padding(x_intervals),
            vertical_padding=_derive_padding(y_intervals),
            outer_margin=max(0, min(x_intervals[0][0], y_intervals[0][0], w - x_intervals[-1][1], h - y_intervals[-1][1])),
        )
        return GridDetectionResult(settings, 'medium', 'Griglia stimata da linee/separatori uniformi su immagine opaca.')

    # Last-resort proposal: one frame covering the whole sheet, deliberately low confidence.
    return GridDetectionResult(
        GridSliceSettings(frame_width=w, frame_height=h, rows=1, columns=1),
        'low',
        'Nessuna griglia regolare affidabile rilevata: proposta l\'intera immagine come singolo frame.',
    )


def grid_rectangles(image_width: int, image_height: int, settings: GridSliceSettings) -> list[tuple[int, int, int, int]]:
    s = settings.normalized()
    rects: list[tuple[int, int, int, int]] = []
    coords: list[tuple[int, int]] = []
    if s.reading_order == 'row_major':
        coords = [(row, col) for row in range(s.rows) for col in range(s.columns)]
    else:
        coords = [(row, col) for col in range(s.columns) for row in range(s.rows)]
    for row, col in coords:
        x = s.outer_margin + col * (s.frame_width + s.horizontal_padding)
        y = s.outer_margin + row * (s.frame_height + s.vertical_padding)
        x2 = x + s.frame_width
        y2 = y + s.frame_height
        if x < 0 or y < 0 or x2 > int(image_width) or y2 > int(image_height):
            raise ValueError(
                f'La cella r{row + 1} c{col + 1} ({x},{y},{x2},{y2}) supera i limiti {image_width}×{image_height}.'
            )
        rects.append((x, y, s.frame_width, s.frame_height))
    return rects


@perf_instrument('spritesheet.slice_regular_sheet')
def slice_regular_sheet(image_rgba: np.ndarray, settings: GridSliceSettings) -> tuple[list[np.ndarray], list[tuple[int, int, int, int]]]:
    rgba = ensure_rgba(image_rgba)
    rects = grid_rectangles(rgba.shape[1], rgba.shape[0], settings)
    frames = [rgba[y:y + h, x:x + w].copy() for x, y, w, h in rects]
    return frames, rects


@perf_instrument('spritesheet.detect_atlas_regions')
def detect_atlas_regions(image_rgba: np.ndarray, *, min_area: int = 8, alpha_threshold: int = 8) -> list[AtlasRegion]:
    rgba = ensure_rgba(image_rgba)
    alpha = rgba[:, :, 3]
    if not np.any(alpha <= alpha_threshold):
        return []
    mask = (alpha > int(alpha_threshold)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    regions: list[AtlasRegion] = []
    for label in range(1, count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < max(1, int(min_area)):
            continue
        regions.append(AtlasRegion(x=x, y=y, width=width, height=height, area=area))
    regions.sort(key=lambda region: (region.y, region.x))
    return regions


def extract_atlas_frames(image_rgba: np.ndarray, regions: Sequence[AtlasRegion]) -> list[np.ndarray]:
    rgba = ensure_rgba(image_rgba)
    frames: list[np.ndarray] = []
    for region in regions:
        x, y, w, h = int(region.x), int(region.y), int(region.width), int(region.height)
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > rgba.shape[1] or y + h > rgba.shape[0]:
            raise ValueError(f'Regione atlas fuori limiti: {region}')
        frames.append(rgba[y:y + h, x:x + w].copy())
    return frames


def normalize_frames_to_canvas(
    frames: Sequence[np.ndarray],
    *,
    alignment: str = 'bottom_center',
) -> tuple[list[np.ndarray], tuple[int, int], list[tuple[int, int]]]:
    if not frames:
        raise ValueError('Nessun frame da normalizzare.')
    rgba_frames = [ensure_rgba(frame) for frame in frames]
    canvas_w = max(frame.shape[1] for frame in rgba_frames)
    canvas_h = max(frame.shape[0] for frame in rgba_frames)
    result: list[np.ndarray] = []
    offsets: list[tuple[int, int]] = []
    for frame in rgba_frames:
        h, w = frame.shape[:2]
        if alignment == 'bottom_center':
            x = (canvas_w - w) // 2
            y = canvas_h - h
        elif alignment == 'center':
            x = (canvas_w - w) // 2
            y = (canvas_h - h) // 2
        elif alignment == 'top_left':
            x = 0
            y = 0
        else:
            raise ValueError(f'Allineamento canvas non supportato: {alignment}')
        canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
        canvas[y:y + h, x:x + w] = frame
        result.append(canvas)
        offsets.append((x, y))
    return result, (canvas_w, canvas_h), offsets


def create_reference_sheet(
    frames: Sequence[np.ndarray],
    indices: Sequence[int],
    *,
    columns: int = 4,
    padding: int = 8,
) -> tuple[np.ndarray, dict]:
    if not indices:
        raise ValueError('Selezionare almeno un frame per la reference sheet.')
    selected: list[np.ndarray] = []
    normalized_indices: list[int] = []
    for value in indices:
        index = int(value)
        if index < 0 or index >= len(frames):
            raise IndexError(f'Indice frame fuori intervallo: {index}')
        selected.append(ensure_rgba(frames[index]))
        normalized_indices.append(index)
    columns = max(1, min(int(columns), len(selected)))
    padding = max(0, int(padding))
    cell_w = max(frame.shape[1] for frame in selected)
    cell_h = max(frame.shape[0] for frame in selected)
    rows = (len(selected) + columns - 1) // columns
    sheet_w = padding * (columns + 1) + cell_w * columns
    sheet_h = padding * (rows + 1) + cell_h * rows
    sheet = np.zeros((sheet_h, sheet_w, 4), dtype=np.uint8)
    placements: list[dict] = []
    for order, (source_index, frame) in enumerate(zip(normalized_indices, selected)):
        row, col = divmod(order, columns)
        h, w = frame.shape[:2]
        cell_x = padding + col * (cell_w + padding)
        cell_y = padding + row * (cell_h + padding)
        x = cell_x + (cell_w - w) // 2
        y = cell_y + (cell_h - h) // 2
        sheet[y:y + h, x:x + w] = frame
        placements.append({'source_index': source_index, 'x': x, 'y': y, 'width': w, 'height': h})
    manifest = {
        'schema': 1,
        'selected_indices': normalized_indices,
        'columns': columns,
        'rows': rows,
        'padding': padding,
        'cell_width': cell_w,
        'cell_height': cell_h,
        'placements': placements,
    }
    return sheet, manifest


def save_rgba_png(path: str | Path, rgba: np.ndarray) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    arr = ensure_rgba(rgba)
    bgra = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
    if not cv2.imwrite(str(target), bgra):
        raise OSError(f'Impossibile salvare PNG: {target}')


def save_sequence_manifest(
    manifest_path: str | Path,
    *,
    source_sheet: str | Path,
    frame_paths: Sequence[str | Path],
    fps: float,
    extraction: dict,
    source_indices: Sequence[int] | None = None,
) -> Path:
    target = Path(manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    relative_paths: list[str] = []
    for frame_path in frame_paths:
        path = Path(frame_path)
        try:
            relative_paths.append(path.resolve().relative_to(target.parent.resolve()).as_posix())
        except Exception:
            relative_paths.append(str(path.resolve()))
    payload = {
        'schema': 1,
        'kind': 'sprite_sequence',
        'source_sheet': str(Path(source_sheet).resolve()),
        'fps': float(fps),
        'frame_paths': relative_paths,
        'source_indices': [int(v) for v in (source_indices or range(len(frame_paths)))],
        'extraction': extraction,
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return target


def load_sequence_manifest(manifest_path: str | Path) -> dict:
    path = Path(manifest_path)
    payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('kind') != 'sprite_sequence' or not isinstance(payload.get('frame_paths'), list):
        raise ValueError('Manifest sequenza sprite non valido.')
    resolved: list[str] = []
    for value in payload['frame_paths']:
        candidate = Path(str(value))
        if not candidate.is_absolute():
            candidate = path.parent / candidate
        resolved.append(str(candidate.resolve()))
    result = dict(payload)
    result['frame_paths'] = resolved
    result['manifest_path'] = str(path.resolve())
    return result
