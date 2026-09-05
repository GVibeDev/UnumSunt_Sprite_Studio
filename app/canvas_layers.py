from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Iterable, Sequence

import numpy as np


class CanvasRasterRole(str, Enum):
    """Semantic raster roles rendered by the shared CREATE canvas.

    Roles define deterministic paint order only. Pixel/image payloads are owned
    by SharedCreateCanvas, not by this state model and never by ProjectState.
    """

    ONION_PREVIOUS = 'onion_previous'
    ONION_NEXT = 'onion_next'
    CURRENT_FRAME = 'current_frame'


_ROLE_ORDER: dict[CanvasRasterRole, int] = {
    CanvasRasterRole.ONION_PREVIOUS: 10,
    CanvasRasterRole.ONION_NEXT: 20,
    CanvasRasterRole.CURRENT_FRAME: 30,
}


@dataclass(slots=True)
class CanvasRasterLayer:
    layer_id: str
    role: CanvasRasterRole
    visible: bool = True
    opacity: float = 1.0

    def __post_init__(self) -> None:
        self.layer_id = _normalize_layer_id(self.layer_id)
        if not isinstance(self.role, CanvasRasterRole):
            self.role = CanvasRasterRole(str(self.role))
        self.opacity = _normalize_opacity(self.opacity)
        self.visible = bool(self.visible)


class CanvasLayerStack:
    """Qt-independent metadata stack for shared-canvas raster layers.

    The stack deliberately contains no QImage/NumPy payloads. It describes
    which visual layers exist, their semantic role, visibility and opacity.
    SharedCreateCanvas owns the corresponding render buffers.
    """

    def __init__(self) -> None:
        self._layers: dict[str, CanvasRasterLayer] = {}
        self._sequence: dict[str, int] = {}
        self._next_sequence = 0

    def __len__(self) -> int:
        return len(self._layers)

    def __contains__(self, layer_id: object) -> bool:
        if not isinstance(layer_id, str):
            return False
        return layer_id.strip() in self._layers

    def clear(self) -> None:
        self._layers.clear()
        self._sequence.clear()
        self._next_sequence = 0

    def upsert(
        self,
        layer_id: str,
        role: CanvasRasterRole | str,
        *,
        visible: bool = True,
        opacity: float = 1.0,
    ) -> CanvasRasterLayer:
        normalized_id = _normalize_layer_id(layer_id)
        normalized_role = role if isinstance(role, CanvasRasterRole) else CanvasRasterRole(str(role))
        existing = self._layers.get(normalized_id)
        if existing is None:
            layer = CanvasRasterLayer(
                layer_id=normalized_id,
                role=normalized_role,
                visible=visible,
                opacity=opacity,
            )
            self._layers[normalized_id] = layer
            self._sequence[normalized_id] = self._next_sequence
            self._next_sequence += 1
            return layer
        existing.role = normalized_role
        existing.visible = bool(visible)
        existing.opacity = _normalize_opacity(opacity)
        return existing

    def remove(self, layer_id: str) -> None:
        normalized_id = _normalize_layer_id(layer_id)
        self._layers.pop(normalized_id, None)
        self._sequence.pop(normalized_id, None)

    def get(self, layer_id: str) -> CanvasRasterLayer | None:
        return self._layers.get(_normalize_layer_id(layer_id))

    def set_visible(self, layer_id: str, visible: bool) -> None:
        layer = self._require(layer_id)
        layer.visible = bool(visible)

    def set_opacity(self, layer_id: str, opacity: float) -> None:
        layer = self._require(layer_id)
        layer.opacity = _normalize_opacity(opacity)

    def ordered(self, *, visible_only: bool = False) -> tuple[CanvasRasterLayer, ...]:
        layers = list(self._layers.values())
        if visible_only:
            layers = [layer for layer in layers if layer.visible and layer.opacity > 0.0]
        layers.sort(
            key=lambda layer: (
                _ROLE_ORDER[layer.role],
                self._sequence.get(layer.layer_id, 0),
                layer.layer_id,
            )
        )
        return tuple(layers)

    def ids(self, *, visible_only: bool = False) -> tuple[str, ...]:
        return tuple(layer.layer_id for layer in self.ordered(visible_only=visible_only))

    def _require(self, layer_id: str) -> CanvasRasterLayer:
        normalized_id = _normalize_layer_id(layer_id)
        layer = self._layers.get(normalized_id)
        if layer is None:
            raise KeyError(f'Canvas raster layer not found: {normalized_id}')
        return layer


@dataclass(frozen=True, slots=True)
class CanvasSelectionRect:
    """Rectangular selection expressed in image coordinates."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = tuple(float(value) for value in (self.x, self.y, self.width, self.height))
        if any(not isfinite(value) for value in values):
            raise ValueError('Canvas selection values must be finite.')
        if values[2] < 0.0 or values[3] < 0.0:
            raise ValueError('Canvas selection width/height cannot be negative.')
        object.__setattr__(self, 'x', values[0])
        object.__setattr__(self, 'y', values[1])
        object.__setattr__(self, 'width', values[2])
        object.__setattr__(self, 'height', values[3])


@dataclass(frozen=True, slots=True)
class CanvasGuideState:
    """Guide/pivot snapshot expressed in image coordinates."""

    vertical: tuple[float, ...] = ()
    horizontal: tuple[float, ...] = ()
    pivot: tuple[float, float] | None = None
    ground_y: float | None = None

    @classmethod
    def build(
        cls,
        *,
        vertical: Iterable[float] = (),
        horizontal: Iterable[float] = (),
        pivot: tuple[float, float] | None = None,
        ground_y: float | None = None,
    ) -> 'CanvasGuideState':
        normalized_ground = None if ground_y is None else float(ground_y)
        if normalized_ground is not None and not isfinite(normalized_ground):
            raise ValueError('Canvas ground guide must be finite.')
        return cls(
            vertical=_normalize_coordinates(vertical),
            horizontal=_normalize_coordinates(horizontal),
            pivot=None if pivot is None else _normalize_point(pivot),
            ground_y=normalized_ground,
        )


class CanvasImageLayerCache:
    """Presentation-only RGBA cache owned by SharedCreateCanvas.

    This is not an edit buffer and is never project persistence. It only keeps
    render copies for the current frame/onion plus transient overlay adapters.
    """

    def __init__(self) -> None:
        self._current: np.ndarray | None = None
        self._onion: np.ndarray | None = None
        self.selection: CanvasSelectionRect | None = None
        self.guides = CanvasGuideState()
        self.revision = 0

    @property
    def current_shape(self) -> tuple[int, int] | None:
        if self._current is None:
            return None
        height, width, _channels = self._current.shape
        return (int(width), int(height))

    def current_view(self) -> np.ndarray | None:
        return self._current

    def onion_view(self) -> np.ndarray | None:
        return self._onion

    def set_images(
        self,
        current_rgba: np.ndarray | None,
        onion_rgba: np.ndarray | None = None,
    ) -> None:
        current = _normalize_rgba(current_rgba, 'Current frame')
        onion = _normalize_rgba(onion_rgba, 'Onion frame')
        if current is not None and onion is not None and current.shape[:2] != onion.shape[:2]:
            raise ValueError('Current and onion frame dimensions must match.')
        self._current = current
        self._onion = onion
        self.revision += 1

    def set_onion(self, onion_rgba: np.ndarray | None) -> None:
        onion = _normalize_rgba(onion_rgba, 'Onion frame')
        if self._current is not None and onion is not None and self._current.shape[:2] != onion.shape[:2]:
            raise ValueError('Current and onion frame dimensions must match.')
        self._onion = onion
        self.revision += 1

    def clear_images(self) -> None:
        if self._current is None and self._onion is None:
            return
        self._current = None
        self._onion = None
        self.revision += 1

    def set_selection(self, selection: CanvasSelectionRect | None) -> None:
        if selection is not None and not isinstance(selection, CanvasSelectionRect):
            raise TypeError('Canvas selection must be CanvasSelectionRect or None.')
        if selection == self.selection:
            return
        self.selection = selection
        self.revision += 1

    def set_guides(self, guides: CanvasGuideState) -> None:
        if not isinstance(guides, CanvasGuideState):
            raise TypeError('Canvas guides must be CanvasGuideState.')
        if guides == self.guides:
            return
        self.guides = guides
        self.revision += 1


@dataclass(slots=True)
class CanvasOverlayState:
    """Transient non-destructive overlays for the shared CREATE canvas."""

    show_transparency: bool = True
    show_grid: bool = False
    show_guides: bool = True
    show_ground: bool = True
    show_pivot: bool = True
    show_selection: bool = True
    grid_spacing: float = 8.0
    vertical_guides: tuple[float, ...] = ()
    horizontal_guides: tuple[float, ...] = ()
    ground_y: float | None = None
    pivot: tuple[float, float] | None = None
    selection_kind: str | None = None
    selection_rect: tuple[float, float, float, float] | None = None
    selection_points: tuple[tuple[float, float], ...] = ()
    onion_skin_enabled: bool = False
    onion_skin_opacity: float = 0.25
    onion_skin_mode: str = 'off'

    def __post_init__(self) -> None:
        self.grid_spacing = _normalize_positive(self.grid_spacing, 'Grid spacing')
        self.vertical_guides = _normalize_coordinates(self.vertical_guides)
        self.horizontal_guides = _normalize_coordinates(self.horizontal_guides)
        if self.ground_y is not None:
            self.ground_y = float(self.ground_y)
            if not isfinite(self.ground_y):
                raise ValueError('Canvas ground guide must be finite.')
        if self.pivot is not None:
            self.pivot = _normalize_point(self.pivot)
        if self.selection_kind is not None:
            normalized_kind = str(self.selection_kind).strip().lower()
            if normalized_kind not in {'rect', 'polygon'}:
                raise ValueError(f'Unsupported selection overlay kind: {self.selection_kind}')
            self.selection_kind = normalized_kind
        if self.selection_rect is not None:
            self.selection_rect = _normalize_rect(self.selection_rect)
        self.selection_points = tuple(_normalize_point(point) for point in self.selection_points)
        self.onion_skin_opacity = _normalize_opacity(self.onion_skin_opacity)
        self.set_onion_mode(self.onion_skin_mode)

    @property
    def show_checkerboard(self) -> bool:
        return self.show_transparency

    @show_checkerboard.setter
    def show_checkerboard(self, visible: bool) -> None:
        self.show_transparency = bool(visible)

    @property
    def show_pixel_grid(self) -> bool:
        return self.show_grid

    @show_pixel_grid.setter
    def show_pixel_grid(self, visible: bool) -> None:
        self.show_grid = bool(visible)

    def set_grid(self, visible: bool, *, spacing: float | None = None) -> None:
        self.show_grid = bool(visible)
        if spacing is not None:
            self.grid_spacing = _normalize_positive(spacing, 'Grid spacing')

    def set_guides(
        self,
        *,
        vertical: Iterable[float] = (),
        horizontal: Iterable[float] = (),
        ground_y: float | None = None,
    ) -> None:
        self.vertical_guides = _normalize_coordinates(vertical)
        self.horizontal_guides = _normalize_coordinates(horizontal)
        if ground_y is None:
            self.ground_y = None
        else:
            normalized_ground = float(ground_y)
            if not isfinite(normalized_ground):
                raise ValueError('Canvas ground guide must be finite.')
            self.ground_y = normalized_ground

    def set_pivot(self, point: tuple[float, float] | None) -> None:
        self.pivot = None if point is None else _normalize_point(point)

    def set_selection_rect(self, x0: float, y0: float, x1: float, y1: float) -> None:
        left = min(float(x0), float(x1))
        top = min(float(y0), float(y1))
        right = max(float(x0), float(x1))
        bottom = max(float(y0), float(y1))
        self.selection_kind = 'rect'
        self.selection_rect = _normalize_rect((left, top, right - left, bottom - top))
        self.selection_points = ()

    def set_selection_polygon(self, points: Sequence[tuple[float, float]]) -> None:
        normalized = tuple(_normalize_point(point) for point in points)
        if len(normalized) < 3:
            raise ValueError('Selection polygon requires at least three points.')
        self.selection_kind = 'polygon'
        self.selection_points = normalized
        self.selection_rect = None

    def clear_selection(self) -> None:
        self.selection_kind = None
        self.selection_rect = None
        self.selection_points = ()

    def set_onion_opacity(self, value: float) -> None:
        self.onion_skin_opacity = _normalize_opacity(value)

    def set_onion_mode(self, mode: str | None) -> None:
        normalized = str(mode or 'off').strip().lower()
        if normalized not in {'off', 'previous', 'next'}:
            raise ValueError(f'Unsupported onion-skin mode: {mode}')
        self.onion_skin_mode = normalized
        self.onion_skin_enabled = normalized != 'off'


@dataclass(slots=True)
class CanvasVisualState:
    """Transient shared-canvas scene metadata.

    No project JSON and no decoded pixel payloads live here. Document geometry,
    layer metadata and overlays are safe to retain while switching CREATE routes.
    """

    canvas_width: int | None = None
    canvas_height: int | None = None
    layers: CanvasLayerStack = field(default_factory=CanvasLayerStack)
    overlays: CanvasOverlayState = field(default_factory=CanvasOverlayState)

    @property
    def has_document_geometry(self) -> bool:
        return self.canvas_width is not None and self.canvas_height is not None

    @property
    def document_size(self) -> tuple[int, int] | None:
        if not self.has_document_geometry:
            return None
        return (int(self.canvas_width), int(self.canvas_height))

    def set_document_size(self, width: int, height: int) -> None:
        normalized_width = int(width)
        normalized_height = int(height)
        if normalized_width <= 0 or normalized_height <= 0:
            raise ValueError('Canvas document dimensions must be positive.')
        self.canvas_width = normalized_width
        self.canvas_height = normalized_height

    def clear_document_geometry(self) -> None:
        self.canvas_width = None
        self.canvas_height = None

    def clear_scene_metadata(self) -> None:
        self.layers.clear()
        self.overlays = CanvasOverlayState()
        self.clear_document_geometry()


def _normalize_layer_id(layer_id: str) -> str:
    normalized = str(layer_id).strip()
    if not normalized:
        raise ValueError('Canvas layer id cannot be empty.')
    return normalized


def _normalize_opacity(value: float) -> float:
    opacity = float(value)
    if not isfinite(opacity):
        raise ValueError('Canvas layer opacity must be finite.')
    if opacity < 0.0 or opacity > 1.0:
        raise ValueError('Canvas layer opacity must be between 0 and 1.')
    return opacity


def _normalize_positive(value: float, label: str) -> float:
    normalized = float(value)
    if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f'{label} must be a positive finite number.')
    return normalized


def _normalize_coordinates(values: Iterable[float]) -> tuple[float, ...]:
    normalized = tuple(float(value) for value in values)
    if any(not isfinite(value) for value in normalized):
        raise ValueError('Canvas guide coordinates must be finite.')
    return normalized


def _normalize_point(point: tuple[float, float]) -> tuple[float, float]:
    if len(point) != 2:
        raise ValueError('Canvas point must contain exactly two coordinates.')
    x = float(point[0])
    y = float(point[1])
    if not isfinite(x) or not isfinite(y):
        raise ValueError('Canvas point coordinates must be finite.')
    return (x, y)


def _normalize_rect(rect: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if len(rect) != 4:
        raise ValueError('Canvas rectangle must contain x, y, width and height.')
    x, y, width, height = (float(value) for value in rect)
    if any(not isfinite(value) for value in (x, y, width, height)):
        raise ValueError('Canvas rectangle values must be finite.')
    if width < 0.0 or height < 0.0:
        raise ValueError('Canvas rectangle width/height cannot be negative.')
    return (x, y, width, height)


def _normalize_rgba(image: np.ndarray | None, label: str) -> np.ndarray | None:
    if image is None:
        return None
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] != 4:
        raise ValueError(f'{label} must be an HxWx4 RGBA array.')
    if array.shape[0] <= 0 or array.shape[1] <= 0:
        raise ValueError(f'{label} dimensions must be positive.')
    if array.dtype != np.uint8:
        raise ValueError(f'{label} must use uint8 RGBA pixels.')
    return np.ascontiguousarray(array).copy()
