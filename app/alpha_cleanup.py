from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.performance_probe import perf_instrument


@dataclass
class AlphaCleanupSettings:
    remove_islands_min_pixels: int = 0
    fill_holes_max_pixels: int = 0
    tighten_radius: int = 0
    alpha_threshold: int = 8

    def to_dict(self) -> dict:
        return {
            'remove_islands_min_pixels': int(self.remove_islands_min_pixels),
            'fill_holes_max_pixels': int(self.fill_holes_max_pixels),
            'tighten_radius': int(self.tighten_radius),
            'alpha_threshold': int(self.alpha_threshold),
        }


def _validate_rgba(rgba: np.ndarray) -> None:
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError('È richiesta un\'immagine RGBA uint8.')


def _component_stats(mask: np.ndarray) -> tuple[int, np.ndarray, np.ndarray]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8),
        connectivity=8,
    )
    return count, labels, stats


def remove_small_islands(alpha: np.ndarray, min_pixels: int, threshold: int = 8) -> np.ndarray:
    if min_pixels <= 0:
        return alpha.copy()
    solid = (alpha > threshold).astype(np.uint8)
    count, labels, stats = _component_stats(solid)
    result = alpha.copy()
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_pixels:
            result[labels == label] = 0
    return result


def fill_small_holes(alpha: np.ndarray, max_pixels: int, threshold: int = 8) -> np.ndarray:
    if max_pixels <= 0:
        return alpha.copy()
    solid = (alpha > threshold).astype(np.uint8)
    inv = 1 - solid
    count, labels, stats = _component_stats(inv)
    result = alpha.copy()
    h, w = alpha.shape
    border_labels = set(labels[0, :]) | set(labels[h - 1, :]) | set(labels[:, 0]) | set(labels[:, w - 1])
    for label in range(1, count):
        if label in border_labels:
            continue
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area <= max_pixels:
            result[labels == label] = 255
    return result


def tighten_alpha(alpha: np.ndarray, radius: int, threshold: int = 8) -> np.ndarray:
    if radius <= 0:
        return alpha.copy()
    kernel_size = radius * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    solid = (alpha > threshold).astype(np.uint8) * 255
    eroded = cv2.erode(solid, kernel, iterations=1)
    softened = cv2.GaussianBlur(eroded, (0, 0), sigmaX=max(0.5, radius * 0.4))
    return np.clip(softened, 0, 255).astype(np.uint8)


def apply_alpha_cleanup(
    rgba: np.ndarray,
    settings: AlphaCleanupSettings,
) -> np.ndarray:
    _validate_rgba(rgba)
    cleaned = rgba.copy()
    alpha = cleaned[:, :, 3]
    alpha = remove_small_islands(alpha, settings.remove_islands_min_pixels, settings.alpha_threshold)
    alpha = fill_small_holes(alpha, settings.fill_holes_max_pixels, settings.alpha_threshold)
    alpha = tighten_alpha(alpha, settings.tighten_radius, settings.alpha_threshold)
    cleaned[:, :, 3] = alpha
    cleaned[alpha == 0, :3] = 0
    return cleaned


@dataclass(frozen=True)
class AlphaPaintRegion:
    """Result of an in-place brush dab, expressed in source-frame coordinates."""

    left: int
    top: int
    right: int
    bottom: int
    changed: bool

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


def _brush_roi(
    width: int,
    height: int,
    center_x: float,
    center_y: float,
    radius: int,
) -> tuple[int, int, int, int]:
    """Return a conservative integer ROI containing every pixel touched by the circle."""
    r = max(1, int(radius))
    cx = float(center_x)
    cy = float(center_y)
    left = max(0, int(np.floor(cx - r)))
    top = max(0, int(np.floor(cy - r)))
    right = min(int(width), int(np.ceil(cx + r)) + 1)
    bottom = min(int(height), int(np.ceil(cy + r)) + 1)
    return left, top, right, bottom


@perf_instrument('cleanup.paint_alpha_circle_roi_inplace')
def paint_alpha_circle_inplace(
    rgba: np.ndarray,
    center_x: float,
    center_y: float,
    radius: int,
    mode: str,
) -> AlphaPaintRegion:
    """Apply one brush dab in-place, allocating only inside the affected ROI.

    R5e13b deliberately keeps the exact R5e12/R5e13a pixel rule while avoiding
    a full-frame copy and a full-frame ``ogrid`` for every mouse movement.
    """
    _validate_rgba(rgba)
    h, w = rgba.shape[:2]
    left, top, right, bottom = _brush_roi(w, h, center_x, center_y, radius)
    if right <= left or bottom <= top:
        return AlphaPaintRegion(left, top, right, bottom, False)

    r = max(1, int(radius))
    yy, xx = np.ogrid[top:bottom, left:right]
    mask = (xx - float(center_x)) ** 2 + (yy - float(center_y)) ** 2 <= r ** 2
    roi = rgba[top:bottom, left:right]

    if mode == 'erase':
        changed = bool(np.any(roi[mask] != 0))
        if changed:
            roi[mask] = (0, 0, 0, 0)
    elif mode == 'restore':
        # Historical behaviour restores opacity and preserves the current RGB.
        # Transparent black therefore remains black, exactly as in R5e13a.
        changed = bool(np.any(roi[:, :, 3][mask] != 255))
        if changed:
            alpha = roi[:, :, 3]
            alpha[mask] = 255
    else:
        raise ValueError(f'Modalità pennello non supportata: {mode}')

    return AlphaPaintRegion(left, top, right, bottom, changed)


@perf_instrument('cleanup.paint_alpha_circle')
def paint_alpha_circle(
    rgba: np.ndarray,
    center_x: float,
    center_y: float,
    radius: int,
    mode: str,
) -> np.ndarray:
    """Compatibility API: return a copied frame with one optimized ROI dab applied."""
    _validate_rgba(rgba)
    result = rgba.copy()
    paint_alpha_circle_inplace(result, center_x, center_y, radius, mode)
    return result


def map_zoomed_point_to_source(
    widget_x: float,
    widget_y: float,
    zoom: int,
    image_width: int,
    image_height: int,
) -> tuple[float, float]:
    """Map a point from the zoomed cleanup canvas into source-frame coordinates."""
    zoom = max(1, int(zoom))
    image_width = max(1, int(image_width))
    image_height = max(1, int(image_height))
    source_x = float(widget_x) / float(zoom)
    source_y = float(widget_y) / float(zoom)
    return (
        max(0.0, min(float(image_width) - 1e-6, source_x)),
        max(0.0, min(float(image_height) - 1e-6, source_y)),
    )


def rectangle_selection_mask(
    image_height: int,
    image_width: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> np.ndarray:
    """Create a boolean source-coordinate selection mask from a drag rectangle."""
    h = int(image_height)
    w = int(image_width)
    if h <= 0 or w <= 0:
        raise ValueError('Dimensioni immagine non valide.')
    left = max(0, min(w - 1, int(np.floor(min(float(x0), float(x1))))))
    top = max(0, min(h - 1, int(np.floor(min(float(y0), float(y1))))))
    right = max(left + 1, min(w, int(np.ceil(max(float(x0), float(x1))))))
    bottom = max(top + 1, min(h, int(np.ceil(max(float(y0), float(y1))))))
    mask = np.zeros((h, w), dtype=bool)
    mask[top:bottom, left:right] = True
    return mask


def polygon_selection_mask(
    image_height: int,
    image_width: int,
    points: list[tuple[float, float]] | tuple[tuple[float, float], ...],
) -> np.ndarray:
    """Rasterize a polygon defined in source-frame coordinates into a boolean mask."""
    h = int(image_height)
    w = int(image_width)
    if h <= 0 or w <= 0:
        raise ValueError('Dimensioni immagine non valide.')
    if len(points) < 3:
        raise ValueError('Una selezione poligonale richiede almeno tre vertici.')
    polygon = np.array(
        [
            [
                max(0, min(w - 1, int(round(float(x))))),
                max(0, min(h - 1, int(round(float(y))))),
            ]
            for x, y in points
        ],
        dtype=np.int32,
    )
    mask_u8 = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask_u8, [polygon], 1)
    return mask_u8.astype(bool)


def erase_alpha_selection(rgba: np.ndarray, selection_mask: np.ndarray) -> np.ndarray:
    """Erase the selected source pixels by setting them to fully transparent black."""
    _validate_rgba(rgba)
    selection = np.asarray(selection_mask, dtype=bool)
    if selection.shape != rgba.shape[:2]:
        raise ValueError('La selezione non coincide con le dimensioni del frame sorgente.')
    result = rgba.copy()
    result[selection] = (0, 0, 0, 0)
    return result


def selection_mask_matches_rgba(rgba: np.ndarray, selection_mask: np.ndarray) -> bool:
    """Return True when the boolean selection mask is compatible with the RGBA frame size."""
    _validate_rgba(rgba)
    selection = np.asarray(selection_mask, dtype=bool)
    return selection.shape == rgba.shape[:2]


def erase_alpha_selection_batch(
    rgba_by_frame: dict[int, np.ndarray],
    selection_mask: np.ndarray,
) -> dict[int, np.ndarray]:
    """Apply the same erase-selection operation to multiple equally-sized frames."""
    result: dict[int, np.ndarray] = {}
    expected_shape: tuple[int, int] | None = None
    selection = np.asarray(selection_mask, dtype=bool)
    for frame_index, rgba in rgba_by_frame.items():
        _validate_rgba(rgba)
        shape = rgba.shape[:2]
        if expected_shape is None:
            expected_shape = shape
        elif shape != expected_shape:
            raise ValueError('I frame selezionati non hanno tutti la stessa dimensione.')
        if selection.shape != shape:
            raise ValueError('La selezione non coincide con le dimensioni del frame sorgente.')
        edited = rgba.copy()
        edited[selection] = (0, 0, 0, 0)
        result[int(frame_index)] = edited
    return result
