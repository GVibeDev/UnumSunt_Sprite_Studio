from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.performance_probe import perf_instrument
from app.models import BackgroundColorRule, ChromaKeySettings


class EmptySubjectError(ValueError):
    """Raised when no opaque subject can be found in the keyed frame."""


@dataclass(frozen=True)
class BackgroundDiagnostic:
    detected_rgb: tuple[int, int, int]
    requested_rgb: tuple[int, int, int] | None
    lab_distance: float | None
    corner_spread: float
    confidence: str
    mismatch: bool
    recommended_mode: str

    def to_dict(self) -> dict:
        return {
            "detected_rgb": list(self.detected_rgb),
            "requested_rgb": list(self.requested_rgb) if self.requested_rgb else None,
            "lab_distance": None if self.lab_distance is None else round(float(self.lab_distance), 4),
            "corner_spread": round(float(self.corner_spread), 4),
            "confidence": self.confidence,
            "mismatch": bool(self.mismatch),
            "recommended_mode": self.recommended_mode,
        }


def _validate_rgb_image(image_rgb: np.ndarray) -> None:
    if not isinstance(image_rgb, np.ndarray):
        raise TypeError('The image must be a NumPy array.')
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError('The RGB image must have shape H×W×3.')
    if image_rgb.dtype != np.uint8:
        raise ValueError('The RGB image must use uint8 values.')


def _corner_pixels(image_rgb: np.ndarray, patch_fraction: float = 0.06) -> np.ndarray:
    height, width, _ = image_rgb.shape
    patch_h = max(2, int(round(height * patch_fraction)))
    patch_w = max(2, int(round(width * patch_fraction)))
    patches = [
        image_rgb[:patch_h, :patch_w],
        image_rgb[:patch_h, width - patch_w :],
        image_rgb[height - patch_h :, :patch_w],
        image_rgb[height - patch_h :, width - patch_w :],
    ]
    return np.concatenate([patch.reshape(-1, 3) for patch in patches], axis=0)


def auto_detect_background_rgb(
    image_rgb: np.ndarray,
    patch_fraction: float = 0.06,
) -> tuple[int, int, int]:
    """Estimate a flat background color from four corner patches."""
    _validate_rgb_image(image_rgb)
    pixels = _corner_pixels(image_rgb, patch_fraction)
    median = np.median(pixels, axis=0)
    return tuple(int(round(value)) for value in median)


def _rgb_color_to_lab(background_rgb: tuple[int, int, int]) -> np.ndarray:
    color = np.array([[background_rgb]], dtype=np.uint8)
    return cv2.cvtColor(color, cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)


def analyze_background(
    image_rgb: np.ndarray,
    requested_rgb: tuple[int, int, int] | None = None,
    patch_fraction: float = 0.06,
    mismatch_threshold: float = 18.0,
) -> BackgroundDiagnostic:
    _validate_rgb_image(image_rgb)
    pixels = _corner_pixels(image_rgb, patch_fraction)
    detected = auto_detect_background_rgb(image_rgb, patch_fraction)
    pixels_lab = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    detected_lab = _rgb_color_to_lab(detected)
    corner_spread = float(np.median(np.linalg.norm(pixels_lab - detected_lab, axis=1)))
    if corner_spread <= 4.0:
        confidence = "alta"
    elif corner_spread <= 12.0:
        confidence = "media"
    else:
        confidence = "bassa"

    distance: float | None = None
    mismatch = False
    if requested_rgb is not None:
        distance = float(np.linalg.norm(detected_lab - _rgb_color_to_lab(requested_rgb)))
        mismatch = distance >= float(mismatch_threshold)

    r, g, b = detected
    luminance = (299 * r + 587 * g + 114 * b) / 1000.0
    chroma_range = max(detected) - min(detected)
    recommended = "edge_connected" if mismatch or luminance < 82 or chroma_range < 35 else "global"
    return BackgroundDiagnostic(
        detected_rgb=detected,
        requested_rgb=requested_rgb,
        lab_distance=distance,
        corner_spread=corner_spread,
        confidence=confidence,
        mismatch=mismatch,
        recommended_mode=recommended,
    )


def _distance_to_background(image_rgb: np.ndarray, background_rgb: tuple[int, int, int]) -> np.ndarray:
    image_lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    background_lab = _rgb_color_to_lab(background_rgb)
    return np.linalg.norm(image_lab - background_lab, axis=2)


def _enabled_background_rules(settings: ChromaKeySettings) -> list[BackgroundColorRule]:
    rules = [BackgroundColorRule(rgb=tuple(settings.background_rgb), enabled=True, tolerance=int(settings.tolerance))]
    for rule in settings.additional_background_colors[:16]:
        if rule.enabled:
            rules.append(rule)
    return rules


def _multi_background_components(
    image_rgb: np.ndarray,
    settings: ChromaKeySettings,
) -> tuple[list[np.ndarray], list[int], list[tuple[int, int, int]]]:
    distances: list[np.ndarray] = []
    tolerances: list[int] = []
    colors: list[tuple[int, int, int]] = []
    for rule in _enabled_background_rules(settings):
        colors.append(tuple(int(v) for v in rule.rgb))
        tolerances.append(rule.normalized_tolerance(int(settings.tolerance)))
        distances.append(_distance_to_background(image_rgb, colors[-1]))
    return distances, tolerances, colors


def _classic_alpha_from_distance(distance: np.ndarray, tolerance: int, softness: int) -> np.ndarray:
    if softness == 0:
        alpha = np.where(distance > tolerance, 255.0, 0.0)
    else:
        alpha = ((distance - tolerance) / float(softness)) * 255.0
        alpha = np.clip(alpha, 0.0, 255.0)
    return alpha.astype(np.uint8)


def _border_connected_region(candidate: np.ndarray) -> np.ndarray:
    """Return candidate pixels connected to any image border using 8-connectivity."""
    height, width = candidate.shape
    binary = candidate.astype(np.uint8)
    count, labels = cv2.connectedComponents(binary, connectivity=8)
    if count <= 1:
        return np.zeros_like(candidate, dtype=bool)
    border_labels = np.unique(
        np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
    )
    border_labels = border_labels[border_labels != 0]
    if border_labels.size == 0:
        return np.zeros_like(candidate, dtype=bool)
    return np.isin(labels, border_labels)


def _edge_connected_alpha_from_distance(
    distance: np.ndarray,
    tolerance: int,
    softness: int,
) -> np.ndarray:
    # The outer candidate includes the softness band so compressed halos remain
    # connected to the real background. Dark or similarly coloured details fully
    # enclosed by the subject are deliberately preserved.
    candidate = distance <= float(tolerance + max(0, softness))
    connected = _border_connected_region(candidate)
    classic = _classic_alpha_from_distance(distance, tolerance, softness)
    alpha = np.full(distance.shape, 255, dtype=np.uint8)
    alpha[connected] = classic[connected]
    return alpha


def resolve_keying_mode(settings: ChromaKeySettings) -> str:
    mode = str(settings.keying_mode or "auto").strip().lower()
    if mode in {"global", "edge_connected"}:
        return mode
    r, g, b = settings.background_rgb
    luminance = (299 * r + 587 * g + 114 * b) / 1000.0
    chroma_range = max(settings.background_rgb) - min(settings.background_rgb)
    if settings.background_mismatch or luminance < 82 or chroma_range < 35:
        return "edge_connected"
    return "global"


@dataclass(frozen=True)
class StructuralMaskDiagnostic:
    background_candidate: np.ndarray
    subject_mask: np.ndarray
    subject_detected: bool
    subject_confidence: str
    subject_reason: str
    outer_border_mask_px: int
    subject_edge_mask_expand_px: int


def _normalized_outer_border_px(settings: ChromaKeySettings, shape: tuple[int, int]) -> int:
    height, width = shape
    maximum = max(0, min(height, width) // 4)
    return max(0, min(maximum, int(settings.outer_border_mask_px)))


def _normalized_subject_expand_px(settings: ChromaKeySettings) -> int:
    return max(0, min(16, int(settings.subject_edge_mask_expand_px)))


def _make_outer_border_mask(shape: tuple[int, int], thickness: int) -> np.ndarray:
    height, width = shape
    result = np.zeros((height, width), dtype=bool)
    n = max(0, min(int(thickness), min(height, width) // 4))
    if n <= 0:
        return result
    result[:n, :] = True
    result[-n:, :] = True
    result[:, :n] = True
    result[:, -n:] = True
    return result


def _hard_background_candidate(
    distances: list[np.ndarray],
    tolerances: list[int],
) -> np.ndarray:
    candidates = [distance <= float(tolerance) for distance, tolerance in zip(distances, tolerances)]
    if not candidates:
        raise ValueError('No background color available.')
    return np.logical_or.reduce(candidates)


def _connected_region_from_seed(candidate: np.ndarray, seed_mask: np.ndarray) -> np.ndarray:
    if candidate.shape != seed_mask.shape:
        raise ValueError('Candidate and seed masks must have the same dimensions.')
    binary = candidate.astype(np.uint8)
    count, labels = cv2.connectedComponents(binary, connectivity=8)
    if count <= 1:
        return np.zeros_like(candidate, dtype=bool)
    seed_labels = np.unique(labels[np.logical_and(seed_mask, candidate)])
    seed_labels = seed_labels[seed_labels != 0]
    if seed_labels.size == 0:
        return np.zeros_like(candidate, dtype=bool)
    return np.isin(labels, seed_labels)


def _detect_central_subject(alpha: np.ndarray) -> tuple[np.ndarray, bool, str, str]:
    if alpha.ndim != 2:
        raise ValueError('The alpha mask must be two-dimensional.')
    height, width = alpha.shape
    foreground = alpha > 8
    binary = foreground.astype(np.uint8)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    empty = np.zeros_like(foreground, dtype=bool)
    if count <= 1:
        return empty, False, 'none', 'no foreground component'

    x0 = int(round(width * 0.25))
    x1 = int(round(width * 0.75))
    y0 = int(round(height * 0.15))
    y1 = int(round(height * 0.85))
    roi = np.zeros_like(foreground, dtype=bool)
    roi[y0:y1, x0:x1] = True
    frame_area = height * width
    minimum_area = max(16, int(round(frame_area * 0.0025)))
    maximum_area = max(1, int(round(frame_area * 0.90)))

    candidates: list[tuple[int, int, bool, bool]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < minimum_area or area > maximum_area:
            continue
        component = labels == label
        intersects_roi = bool(np.any(component & roi))
        left = int(stats[label, cv2.CC_STAT_LEFT])
        top = int(stats[label, cv2.CC_STAT_TOP])
        comp_w = int(stats[label, cv2.CC_STAT_WIDTH])
        comp_h = int(stats[label, cv2.CC_STAT_HEIGHT])
        touches_border = left <= 0 or top <= 0 or left + comp_w >= width or top + comp_h >= height
        candidates.append((label, area, intersects_roi, touches_border))

    central = [item for item in candidates if item[2]]
    if central:
        label, area, _central, touches_border = max(central, key=lambda item: item[1])
        component = labels == label
        confidence = 'media' if touches_border else 'alta'
        reason = 'largest component intersecting the central ROI'
        return component, True, confidence, reason

    fallback = [item for item in candidates if not item[3]]
    if fallback:
        label, _area, _central, _touches = max(fallback, key=lambda item: item[1])
        return labels == label, True, 'media', 'largest foreground component not connected to the border'

    return empty, False, 'none', 'no reliable central subject detected'


def _legacy_alpha_mask(
    image_rgb: np.ndarray,
    settings: ChromaKeySettings,
) -> np.ndarray:
    softness = max(0, int(settings.softness))
    cleanup_radius = min(max(0, int(settings.cleanup_radius)), 9)
    distances, tolerances, _colors = _multi_background_components(image_rgb, settings)
    mode = resolve_keying_mode(settings)

    # Exact R5e5-B path. This helper is deliberately kept byte-for-byte in
    # behaviour for the default structural settings (0 / 0).
    if len(distances) == 1:
        distance = distances[0]
        tolerance = tolerances[0]
        if mode == "edge_connected":
            mask = _edge_connected_alpha_from_distance(distance, tolerance, softness)
        else:
            mask = _classic_alpha_from_distance(distance, tolerance, softness)
    else:
        classic_masks = [
            _classic_alpha_from_distance(distance, tolerance, softness)
            for distance, tolerance in zip(distances, tolerances)
        ]
        combined_classic = np.minimum.reduce(classic_masks)
        if mode == "edge_connected":
            candidates = [
                distance <= float(tolerance + softness)
                for distance, tolerance in zip(distances, tolerances)
            ]
            combined_candidate = np.logical_or.reduce(candidates)
            connected = _border_connected_region(combined_candidate)
            mask = np.full(combined_classic.shape, 255, dtype=np.uint8)
            mask[connected] = combined_classic[connected]
        else:
            mask = combined_classic

    if cleanup_radius > 0:
        kernel_size = cleanup_radius * 2 + 1
        mask = cv2.medianBlur(mask, kernel_size)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def _structural_alpha_mask(
    image_rgb: np.ndarray,
    settings: ChromaKeySettings,
) -> tuple[np.ndarray, StructuralMaskDiagnostic]:
    softness = max(0, int(settings.softness))
    cleanup_radius = min(max(0, int(settings.cleanup_radius)), 9)
    distances, tolerances, _colors = _multi_background_components(image_rgb, settings)
    mode = resolve_keying_mode(settings)
    classic_masks = [
        _classic_alpha_from_distance(distance, tolerance, softness)
        for distance, tolerance in zip(distances, tolerances)
    ]
    combined_classic = np.minimum.reduce(classic_masks)
    hard_candidate = _hard_background_candidate(distances, tolerances)
    outer_px = _normalized_outer_border_px(settings, combined_classic.shape)
    outer_mask = _make_outer_border_mask(combined_classic.shape, outer_px)

    if mode == 'edge_connected':
        connectivity_candidates = [
            distance <= float(tolerance + softness)
            for distance, tolerance in zip(distances, tolerances)
        ]
        combined_candidate = np.logical_or.reduce(connectivity_candidates)
        if outer_px > 0:
            # The forced strip is both guaranteed background and a connectivity seed.
            seeded_candidate = np.logical_or(combined_candidate, outer_mask)
            connected = _connected_region_from_seed(seeded_candidate, outer_mask)
        else:
            connected = _border_connected_region(combined_candidate)
        mask = np.full(combined_classic.shape, 255, dtype=np.uint8)
        mask[connected] = combined_classic[connected]
    else:
        mask = combined_classic.copy()

    if outer_px > 0:
        mask[outer_mask] = 0
        hard_candidate = np.logical_or(hard_candidate, outer_mask)

    subject_mask, detected, confidence, reason = _detect_central_subject(mask)
    expand_px = _normalized_subject_expand_px(settings)
    if expand_px > 0 and detected:
        kernel_size = expand_px * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        eroded_subject = cv2.erode(subject_mask.astype(np.uint8), kernel, iterations=1).astype(bool)
        removed_fringe = np.logical_and(subject_mask, np.logical_not(eroded_subject))
        mask[removed_fringe] = 0

    if cleanup_radius > 0:
        kernel_size = cleanup_radius * 2 + 1
        mask = cv2.medianBlur(mask, kernel_size)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        if outer_px > 0:
            # Morphological cleanup must never reopen the forced border.
            mask[outer_mask] = 0

    diagnostic = StructuralMaskDiagnostic(
        background_candidate=(hard_candidate.astype(np.uint8) * 255),
        subject_mask=(subject_mask.astype(np.uint8) * 255),
        subject_detected=bool(detected),
        subject_confidence=confidence,
        subject_reason=reason,
        outer_border_mask_px=outer_px,
        subject_edge_mask_expand_px=(expand_px if detected else 0),
    )
    return mask, diagnostic


@perf_instrument('chroma.create_alpha_mask_with_diagnostics')
def create_alpha_mask_with_diagnostics(
    image_rgb: np.ndarray,
    settings: ChromaKeySettings,
) -> tuple[np.ndarray, StructuralMaskDiagnostic]:
    _validate_rgb_image(image_rgb)
    outer_px = _normalized_outer_border_px(settings, image_rgb.shape[:2])
    expand_px = _normalized_subject_expand_px(settings)
    if outer_px > 0 or expand_px > 0:
        return _structural_alpha_mask(image_rgb, settings)

    mask = _legacy_alpha_mask(image_rgb, settings)
    distances, tolerances, _colors = _multi_background_components(image_rgb, settings)
    hard_candidate = _hard_background_candidate(distances, tolerances)
    subject_mask, detected, confidence, reason = _detect_central_subject(mask)
    diagnostic = StructuralMaskDiagnostic(
        background_candidate=(hard_candidate.astype(np.uint8) * 255),
        subject_mask=(subject_mask.astype(np.uint8) * 255),
        subject_detected=bool(detected),
        subject_confidence=confidence,
        subject_reason=reason,
        outer_border_mask_px=0,
        subject_edge_mask_expand_px=0,
    )
    return mask, diagnostic


def create_alpha_mask(
    image_rgb: np.ndarray,
    settings: ChromaKeySettings,
) -> np.ndarray:
    _validate_rgb_image(image_rgb)
    outer_px = _normalized_outer_border_px(settings, image_rgb.shape[:2])
    expand_px = _normalized_subject_expand_px(settings)
    if outer_px <= 0 and expand_px <= 0:
        return _legacy_alpha_mask(image_rgb, settings)
    mask, _diagnostic = _structural_alpha_mask(image_rgb, settings)
    return mask

def _decontaminate_edges(
    image_rgb: np.ndarray,
    alpha: np.ndarray,
    background_rgb: tuple[int, int, int],
    strength: int,
) -> np.ndarray:
    strength_float = np.clip(strength / 100.0, 0.0, 1.0)
    if strength_float <= 0:
        return image_rgb.copy()
    source = image_rgb.astype(np.float32)
    bg = np.array(background_rgb, dtype=np.float32).reshape(1, 1, 3)
    a = alpha.astype(np.float32)[..., None] / 255.0
    safe_a = np.maximum(a, 0.10)
    estimated_fg = (source - bg * (1.0 - a)) / safe_a
    estimated_fg = np.clip(estimated_fg, 0.0, 255.0)
    edge_weight = (1.0 - np.abs(a * 2.0 - 1.0)) * strength_float
    corrected = source * (1.0 - edge_weight) + estimated_fg * edge_weight
    corrected[a[..., 0] <= 0.01] = 0.0
    return np.clip(corrected, 0.0, 255.0).astype(np.uint8)


def _decontaminate_edges_multi(
    image_rgb: np.ndarray,
    alpha: np.ndarray,
    settings: ChromaKeySettings,
) -> np.ndarray:
    enabled = _enabled_background_rules(settings)
    if len(enabled) <= 1:
        return _decontaminate_edges(
            image_rgb, alpha, settings.background_rgb, settings.edge_decontamination
        )
    strength_float = np.clip(settings.edge_decontamination / 100.0, 0.0, 1.0)
    if strength_float <= 0:
        return image_rgb.copy()

    image_lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    labs = np.stack([_rgb_color_to_lab(tuple(rule.rgb)) for rule in enabled], axis=0)
    distances = np.linalg.norm(image_lab[:, :, None, :] - labs[None, None, :, :], axis=3)
    nearest_index = np.argmin(distances, axis=2)
    palette = np.array([rule.rgb for rule in enabled], dtype=np.float32)
    bg = palette[nearest_index]

    source = image_rgb.astype(np.float32)
    a = alpha.astype(np.float32)[..., None] / 255.0
    safe_a = np.maximum(a, 0.10)
    estimated_fg = (source - bg * (1.0 - a)) / safe_a
    estimated_fg = np.clip(estimated_fg, 0.0, 255.0)
    edge_weight = (1.0 - np.abs(a * 2.0 - 1.0)) * strength_float
    corrected = source * (1.0 - edge_weight) + estimated_fg * edge_weight
    corrected[a[..., 0] <= 0.01] = 0.0
    return np.clip(corrected, 0.0, 255.0).astype(np.uint8)


@perf_instrument('chroma.apply_chroma_key_with_diagnostics')
def apply_chroma_key_with_diagnostics(
    image_rgb: np.ndarray,
    settings: ChromaKeySettings,
) -> tuple[np.ndarray, np.ndarray, StructuralMaskDiagnostic]:
    mask, diagnostic = create_alpha_mask_with_diagnostics(image_rgb, settings)
    corrected_rgb = _decontaminate_edges_multi(image_rgb, mask, settings)
    rgba = np.dstack((corrected_rgb, mask))
    rgba[mask == 0, :3] = 0
    return rgba, mask, diagnostic


def apply_chroma_key(
    image_rgb: np.ndarray,
    settings: ChromaKeySettings,
) -> tuple[np.ndarray, np.ndarray]:
    mask = create_alpha_mask(image_rgb, settings)
    corrected_rgb = _decontaminate_edges_multi(image_rgb, mask, settings)
    rgba = np.dstack((corrected_rgb, mask))
    rgba[mask == 0, :3] = 0
    return rgba, mask


def crop_rgba_to_subject(
    rgba: np.ndarray,
    padding: int = 0,
    alpha_threshold: int = 8,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    if not isinstance(rgba, np.ndarray):
        raise TypeError('The image must be a NumPy array.')
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError('The RGBA image must have shape H×W×4 and dtype uint8.')
    alpha = rgba[:, :, 3]
    ys, xs = np.nonzero(alpha > max(0, min(255, alpha_threshold)))
    if len(xs) == 0 or len(ys) == 0:
        raise EmptySubjectError(
            'No subject detected. Reduce tolerance or choose a better background color.'
        )
    height, width = alpha.shape
    pad = max(0, int(padding))
    left = max(0, int(xs.min()) - pad)
    top = max(0, int(ys.min()) - pad)
    right = min(width, int(xs.max()) + 1 + pad)
    bottom = min(height, int(ys.max()) + 1 + pad)
    return rgba[top:bottom, left:right].copy(), (left, top, right, bottom)


@perf_instrument('cleanup.render_checkerboard_region')
def render_checkerboard_region(
    rgba_region: np.ndarray,
    *,
    origin_x: int,
    origin_y: int,
    tile_size: int = 14,
    light: int = 208,
    dark: int = 166,
) -> np.ndarray:
    """Composite an RGBA sub-region over the same globally anchored checkerboard.

    The result is pixel-identical to slicing ``render_checkerboard(full_rgba)`` at
    the same coordinates, but it allocates only for the dirty brush rectangle.
    """
    if rgba_region.ndim != 3 or rgba_region.shape[2] != 4:
        raise ValueError('An RGBA image is required.')
    height, width, _ = rgba_region.shape
    tile = max(2, int(tile_size))
    y_tiles = np.arange(int(origin_y), int(origin_y) + height)[:, None] // tile
    x_tiles = np.arange(int(origin_x), int(origin_x) + width)[None, :] // tile
    checker = ((x_tiles + y_tiles) % 2).astype(np.uint8)
    base = np.where(checker[..., None] == 0, light, dark).astype(np.float32)
    background = np.repeat(base, 3, axis=2)
    rgb = rgba_region[:, :, :3].astype(np.float32)
    alpha = rgba_region[:, :, 3:4].astype(np.float32) / 255.0
    composite = rgb * alpha + background * (1.0 - alpha)
    return np.clip(composite, 0, 255).astype(np.uint8)


@perf_instrument('chroma.render_checkerboard')
def render_checkerboard(
    rgba: np.ndarray,
    tile_size: int = 14,
    light: int = 208,
    dark: int = 166,
) -> np.ndarray:
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError('An RGBA image is required.')
    height, width, _ = rgba.shape
    y_tiles = np.arange(height)[:, None] // max(2, tile_size)
    x_tiles = np.arange(width)[None, :] // max(2, tile_size)
    checker = ((x_tiles + y_tiles) % 2).astype(np.uint8)
    base = np.where(checker[..., None] == 0, light, dark).astype(np.float32)
    background = np.repeat(base, 3, axis=2)
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    composite = rgb * alpha + background * (1.0 - alpha)
    return np.clip(composite, 0, 255).astype(np.uint8)
