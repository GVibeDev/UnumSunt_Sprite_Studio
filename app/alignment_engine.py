from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable, Mapping

import cv2
import numpy as np

from app.chroma_key import apply_chroma_key, crop_rgba_to_subject
from app.performance_probe import perf_instrument
from app.models import AlignmentSettings, ChromaKeySettings, FrameAlignmentState


@dataclass
class SubjectFrame:
    frame_index: int
    rgba: np.ndarray
    crop_box: tuple[int, int, int, int]
    auto_pivot_x: float
    auto_pivot_y: float

    @property
    def width(self) -> int:
        return int(self.rgba.shape[1])

    @property
    def height(self) -> int:
        return int(self.rgba.shape[0])


@dataclass(frozen=True)
class FramePlacement:
    destination_left: int
    destination_top: int
    destination_width: int
    destination_height: int
    scaled_source_pivot_x: float
    scaled_source_pivot_y: float
    visible_box: tuple[int, int, int, int] | None

    def to_dict(self) -> dict:
        return {
            'destination_rect': [
                self.destination_left,
                self.destination_top,
                self.destination_width,
                self.destination_height,
            ],
            'scaled_source_pivot': [
                round(self.scaled_source_pivot_x, 4),
                round(self.scaled_source_pivot_y, 4),
            ],
            'visible_box_canvas': list(self.visible_box) if self.visible_box else None,
        }


def prepare_subject_frame(
    frame_index: int,
    image_rgb: np.ndarray,
    chroma_settings: ChromaKeySettings,
    crop_padding: int = 0,
) -> SubjectFrame:
    rgba, _ = apply_chroma_key(image_rgb, chroma_settings)
    return prepare_subject_frame_from_rgba(frame_index, rgba, crop_padding=crop_padding)


def prepare_subject_frame_from_rgba(
    frame_index: int,
    rgba: np.ndarray,
    crop_padding: int = 0,
) -> SubjectFrame:
    cropped, crop_box = crop_rgba_to_subject(
        rgba,
        padding=max(0, int(crop_padding)),
        alpha_threshold=8,
    )
    pivot_x, pivot_y = estimate_ground_pivot(cropped)
    return SubjectFrame(
        frame_index=int(frame_index),
        rgba=cropped,
        crop_box=crop_box,
        auto_pivot_x=pivot_x,
        auto_pivot_y=pivot_y,
    )


def estimate_ground_pivot(
    rgba: np.ndarray,
    alpha_threshold: int = 16,
    lower_band_fraction: float = 0.10,
) -> tuple[float, float]:
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError('È richiesta un\'immagine RGBA.')
    alpha = rgba[:, :, 3]
    ys, xs = np.nonzero(alpha > max(0, min(255, int(alpha_threshold))))
    if len(xs) == 0:
        raise ValueError('La sagoma non contiene pixel opachi.')
    bottom_y = int(round(float(np.quantile(ys, 0.997))))
    bottom_y = min(bottom_y, int(ys.max()))
    band_height = max(2, int(round(rgba.shape[0] * lower_band_fraction)))
    band_start = max(0, bottom_y - band_height + 1)
    rows = np.indices(alpha.shape)[0]
    lower_mask = (alpha > alpha_threshold) & (rows >= band_start) & (rows <= bottom_y)
    lower_ys, lower_xs = np.nonzero(lower_mask)
    if len(lower_xs) == 0:
        lower_xs = xs
        lower_ys = ys
    weights = alpha[lower_ys, lower_xs].astype(np.float64)
    if weights.sum() > 0:
        pivot_x = float(np.average(lower_xs.astype(np.float64), weights=weights))
    else:
        pivot_x = float(np.median(lower_xs))
    return pivot_x, float(bottom_y + 1)


def estimate_geometric_anchor(
    rgba: np.ndarray,
    alpha_threshold: int = 16,
    vertical_slice: tuple[float, float] = (0.0, 1.0),
    robust_interior_weight: bool = True,
) -> tuple[float, float]:
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError('È richiesta un\'immagine RGBA.')
    alpha = rgba[:, :, 3].astype(np.float32)
    mask = alpha > alpha_threshold
    if not np.any(mask):
        raise ValueError('La sagoma non contiene pixel opachi.')
    top_frac, bottom_frac = vertical_slice
    top_frac = float(np.clip(top_frac, 0.0, 1.0))
    bottom_frac = float(np.clip(bottom_frac, top_frac, 1.0))
    h, w = alpha.shape
    ys, xs = np.nonzero(mask)
    top = int(ys.min())
    bottom = int(ys.max()) + 1
    span = max(1, bottom - top)
    slice_top = top + int(round(span * top_frac))
    slice_bottom = top + int(round(span * bottom_frac))
    slice_bottom = max(slice_top + 1, min(h, slice_bottom))
    region = mask.copy()
    region[:slice_top, :] = False
    region[slice_bottom:, :] = False
    if not np.any(region):
        region = mask
    weights = alpha.copy()
    if robust_interior_weight:
        solid = (alpha > alpha_threshold).astype(np.uint8)
        interior = cv2.distanceTransform(solid, cv2.DIST_L2, 3).astype(np.float32)
        weights *= (1.0 + interior)
    weights[~region] = 0.0
    ys2, xs2 = np.nonzero(weights > 0)
    if len(xs2) == 0:
        ys2, xs2 = np.nonzero(region)
        weights2 = alpha[ys2, xs2].astype(np.float64)
    else:
        weights2 = weights[ys2, xs2].astype(np.float64)
    total = float(weights2.sum())
    if total <= 0:
        return float(xs.mean()), float(ys.mean())
    return (
        float(np.average(xs2.astype(np.float64), weights=weights2)),
        float(np.average(ys2.astype(np.float64), weights=weights2)),
    )


def estimate_anchor_by_mode(rgba: np.ndarray, mode: str) -> tuple[float, float]:
    key = mode.lower().strip()
    if key == 'ground':
        return estimate_ground_pivot(rgba)
    if key == 'centroid':
        return estimate_geometric_anchor(rgba, vertical_slice=(0.0, 1.0), robust_interior_weight=True)
    if key == 'upper_body':
        return estimate_geometric_anchor(rgba, vertical_slice=(0.0, 0.45), robust_interior_weight=True)
    raise ValueError(f'Modalità ancora non supportata: {mode}')


def calculate_shared_fit_scale(subjects: Mapping[int, SubjectFrame], states: Mapping[int, FrameAlignmentState], settings: AlignmentSettings) -> float:
    settings.validate()
    if not subjects:
        raise ValueError('Nessun fotogramma preparato.')
    available_left = max(1e-6, settings.canvas_pivot_x - settings.margin)
    available_right = max(1e-6, settings.canvas_width - settings.canvas_pivot_x - settings.margin)
    available_top = max(1e-6, settings.canvas_pivot_y - settings.margin)
    available_bottom = max(1e-6, settings.canvas_height - settings.canvas_pivot_y - settings.margin)
    ratios: list[float] = []
    for frame_index, subject in subjects.items():
        state = states.get(frame_index)
        if state is None:
            continue
        left_extent = max(0.0, state.source_pivot_x)
        right_extent = max(0.0, subject.width - state.source_pivot_x)
        top_extent = max(0.0, state.source_pivot_y)
        bottom_extent = max(0.0, subject.height - state.source_pivot_y)
        if left_extent > 0: ratios.append(available_left / left_extent)
        if right_extent > 0: ratios.append(available_right / right_extent)
        if top_extent > 0: ratios.append(available_top / top_extent)
        if bottom_extent > 0: ratios.append(available_bottom / bottom_extent)
    if not ratios:
        raise ValueError('Impossibile calcolare la scala condivisa.')
    return float(np.clip(min(ratios), 0.005, 64.0))


@perf_instrument('alignment.resize_rgba_alpha_aware')
def resize_rgba_alpha_aware(rgba: np.ndarray, scale: float) -> np.ndarray:
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError('È richiesta un\'immagine RGBA uint8.')
    if scale <= 0:
        raise ValueError('La scala deve essere positiva.')
    source_h, source_w = rgba.shape[:2]
    target_w = max(1, int(round(source_w * scale)))
    target_h = max(1, int(round(source_h * scale)))
    if target_w == source_w and target_h == source_h:
        return rgba.copy()
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    premultiplied = rgba[:, :, :3].astype(np.float32) * alpha[:, :, None]
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
    resized_alpha = cv2.resize(alpha, (target_w, target_h), interpolation=interpolation)
    resized_premultiplied = cv2.resize(premultiplied, (target_w, target_h), interpolation=interpolation)
    if resized_premultiplied.ndim == 2:
        resized_premultiplied = resized_premultiplied[:, :, None]
    safe_alpha = np.maximum(resized_alpha[:, :, None], 1e-6)
    resized_rgb = np.where(resized_alpha[:, :, None] > 1e-5, resized_premultiplied / safe_alpha, 0.0)
    result = np.dstack((np.clip(resized_rgb, 0, 255).astype(np.uint8), np.clip(resized_alpha * 255.0, 0, 255).astype(np.uint8)))
    result[result[:, :, 3] == 0, :3] = 0
    return result


@perf_instrument('alignment.render_aligned_frame')
def render_aligned_frame(subject: SubjectFrame, state: FrameAlignmentState, settings: AlignmentSettings) -> tuple[np.ndarray, FramePlacement]:
    settings.validate()
    scaled = resize_rgba_alpha_aware(subject.rgba, settings.shared_scale)
    scaled_h, scaled_w = scaled.shape[:2]
    scaled_pivot_x = state.source_pivot_x * settings.shared_scale
    scaled_pivot_y = state.source_pivot_y * settings.shared_scale
    destination_left = int(round(settings.canvas_pivot_x + state.offset_x - scaled_pivot_x))
    destination_top = int(round(settings.canvas_pivot_y + state.offset_y - scaled_pivot_y))
    canvas = np.zeros((settings.canvas_height, settings.canvas_width, 4), dtype=np.uint8)
    source_left = max(0, -destination_left)
    source_top = max(0, -destination_top)
    source_right = min(scaled_w, settings.canvas_width - destination_left)
    source_bottom = min(scaled_h, settings.canvas_height - destination_top)
    visible_box = None
    if source_right > source_left and source_bottom > source_top:
        target_left = max(0, destination_left)
        target_top = max(0, destination_top)
        target_right = target_left + (source_right - source_left)
        target_bottom = target_top + (source_bottom - source_top)
        source_slice = scaled[source_top:source_bottom, source_left:source_right]
        target_slice = canvas[target_top:target_bottom, target_left:target_right]
        source_alpha = source_slice[:, :, 3:4].astype(np.float32) / 255.0
        target_alpha = target_slice[:, :, 3:4].astype(np.float32) / 255.0
        output_alpha = source_alpha + target_alpha * (1.0 - source_alpha)
        source_rgb = source_slice[:, :, :3].astype(np.float32)
        target_rgb = target_slice[:, :, :3].astype(np.float32)
        numerator = source_rgb * source_alpha + target_rgb * target_alpha * (1.0 - source_alpha)
        safe_output_alpha = np.maximum(output_alpha, 1e-6)
        output_rgb = np.where(output_alpha > 1e-6, numerator / safe_output_alpha, 0.0)
        target_slice[:, :, :3] = np.clip(output_rgb, 0, 255).astype(np.uint8)
        target_slice[:, :, 3] = np.clip(output_alpha[:, :, 0] * 255.0, 0, 255).astype(np.uint8)
        visible_box = (target_left, target_top, target_right, target_bottom)
    placement = FramePlacement(destination_left, destination_top, scaled_w, scaled_h, scaled_pivot_x, scaled_pivot_y, visible_box)
    return canvas, placement


@perf_instrument('alignment.create_spritesheet')
def create_spritesheet(frames: Iterable[np.ndarray], layout: str = 'horizontal', columns: int = 8, padding: int = 0) -> tuple[np.ndarray, list[dict], int, int]:
    frame_list = [np.asarray(frame) for frame in frames]
    if not frame_list:
        raise ValueError('Nessun frame per lo sprite sheet.')
    first_shape = frame_list[0].shape
    if len(first_shape) != 3 or first_shape[2] != 4:
        raise ValueError('I frame devono essere RGBA.')
    if any(frame.shape != first_shape for frame in frame_list):
        raise ValueError('Tutti i frame devono avere le stesse dimensioni.')
    frame_h, frame_w = first_shape[:2]
    count = len(frame_list)
    layout_key = layout.lower().strip()
    gap = max(0, int(padding))
    if layout_key == 'horizontal':
        column_count = count; row_count = 1
    elif layout_key == 'vertical':
        column_count = 1; row_count = count
    elif layout_key == 'grid':
        column_count = max(1, min(count, int(columns))); row_count = int(ceil(count / column_count))
    else:
        raise ValueError(f'Layout sprite sheet non supportato: {layout}')
    sheet_w = column_count * frame_w + max(0, column_count - 1) * gap
    sheet_h = row_count * frame_h + max(0, row_count - 1) * gap
    sheet = np.zeros((sheet_h, sheet_w, 4), dtype=np.uint8)
    positions: list[dict] = []
    for index, frame in enumerate(frame_list):
        row = index // column_count
        column = index % column_count
        x = column * (frame_w + gap)
        y = row * (frame_h + gap)
        sheet[y:y + frame_h, x:x + frame_w] = frame
        positions.append({'index': index, 'row': row, 'column': column, 'rect': [x, y, frame_w, frame_h]})
    return sheet, positions, column_count, row_count


def alpha_bounding_box(rgba: np.ndarray, threshold: int = 8) -> tuple[int, int, int, int] | None:
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError('È richiesta un\'immagine RGBA.')
    ys, xs = np.nonzero(rgba[:, :, 3] > threshold)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
