from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from app.alpha_cleanup import map_zoomed_point_to_source


class CleanupCanvas(QWidget):
    brush_stroke_started = Signal(float, float)
    brush_painted = Signal(float, float)
    brush_stroke_finished = Signal()
    rectangle_selected = Signal(float, float, float, float)
    polygon_selected = Signal(object)
    selection_cancelled = Signal()
    delete_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._rgb: np.ndarray | None = None
        self._qimage: QImage | None = None
        self._zoom = 8
        self._show_grid = True
        self._show_alpha_only = False
        self._brush_radius = 1
        self._painting = False
        self._last_cursor_pos: QPoint | None = None
        self._tool_mode = 'brush'
        self._rect_start: tuple[float, float] | None = None
        self._rect_end: tuple[float, float] | None = None
        self._polygon_points: list[tuple[float, float]] = []
        self._polygon_hover: tuple[float, float] | None = None
        self._selection_kind: str | None = None
        self._selection_points: list[tuple[float, float]] = []
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._update_size()

    def sizeHint(self) -> QSize:
        if self._rgb is None:
            return QSize(384, 384)
        return QSize(self._rgb.shape[1] * self._zoom, self._rgb.shape[0] * self._zoom)

    def set_image(self, rgb: np.ndarray | None) -> None:
        if rgb is None:
            self._rgb = None
            self._qimage = None
        else:
            array = np.asarray(rgb)
            if array.ndim != 3 or array.shape[2] != 3 or array.dtype != np.uint8:
                raise ValueError('CleanupCanvas requires an RGB uint8 H×W×3 preview.')
            self._rgb = np.ascontiguousarray(array)
            # The QImage references _rgb directly. Keeping the ndarray as an instance
            # attribute guarantees the backing memory lifetime and removes the former
            # full-frame QImage.copy() from every paintEvent.
            self._qimage = QImage(
                self._rgb.data,
                self._rgb.shape[1],
                self._rgb.shape[0],
                self._rgb.strides[0],
                QImage.Format.Format_RGB888,
            )
        self._update_size()
        self.update()

    def update_image_region(self, rgb_region: np.ndarray, left: int, top: int) -> None:
        """Replace one source-space preview ROI and repaint only its zoomed rectangle."""
        if self._rgb is None:
            return
        region = np.asarray(rgb_region)
        if region.ndim != 3 or region.shape[2] != 3 or region.dtype != np.uint8:
            raise ValueError('The preview region must be RGB uint8 H×W×3.')
        left = int(left)
        top = int(top)
        right = left + int(region.shape[1])
        bottom = top + int(region.shape[0])
        if left < 0 or top < 0 or right > self._rgb.shape[1] or bottom > self._rgb.shape[0]:
            raise ValueError('Preview region is outside the frame bounds.')
        self._rgb[top:bottom, left:right] = region
        margin = max(2, self._zoom // 2)
        dirty = QRect(
            left * self._zoom - margin,
            top * self._zoom - margin,
            region.shape[1] * self._zoom + margin * 2,
            region.shape[0] * self._zoom + margin * 2,
        ).intersected(self.rect())
        if not dirty.isEmpty():
            self.update(dirty)

    def set_zoom(self, zoom: int) -> None:
        self._zoom = max(1, min(32, int(zoom)))
        self._update_size()
        self.update()

    def set_tool_mode(self, mode: str) -> None:
        normalized = str(mode).strip().lower()
        if normalized not in {'brush', 'rectangle', 'polygon'}:
            raise ValueError(f'Unsupported clean-up tool: {mode}')
        if normalized != self._tool_mode:
            if self._painting:
                self._painting = False
                self.brush_stroke_finished.emit()
            self._rect_start = None
            self._rect_end = None
            self._polygon_points = []
            self._polygon_hover = None
        self._tool_mode = normalized
        self.update()

    @property
    def tool_mode(self) -> str:
        return self._tool_mode

    def set_overlays(self, *, show_grid: bool, show_alpha_only: bool, brush_radius: int) -> None:
        self._show_grid = bool(show_grid)
        self._show_alpha_only = bool(show_alpha_only)
        self._brush_radius = max(1, int(brush_radius))
        self.update()

    def clear_selection(self, *, emit_signal: bool = True) -> None:
        self._rect_start = None
        self._rect_end = None
        self._polygon_points = []
        self._polygon_hover = None
        self._selection_kind = None
        self._selection_points = []
        if emit_signal:
            self.selection_cancelled.emit()
        self.update()

    def _update_size(self) -> None:
        if self._rgb is None:
            self.setMinimumSize(384, 384)
            self.updateGeometry()
            return
        self.setFixedSize(self._rgb.shape[1] * self._zoom, self._rgb.shape[0] * self._zoom)
        self.updateGeometry()

    def _source_point(self, event: QMouseEvent) -> tuple[float, float] | None:
        if self._rgb is None:
            return None
        return map_zoomed_point_to_source(
            event.position().x(),
            event.position().y(),
            self._zoom,
            self._rgb.shape[1],
            self._rgb.shape[0],
        )

    def _screen_point(self, source: tuple[float, float]) -> QPointF:
        return QPointF(source[0] * self._zoom, source[1] * self._zoom)

    def _cursor_dirty_rect(self, pos: QPoint | None) -> QRect:
        if pos is None:
            return QRect()
        radius = self._brush_radius * self._zoom
        margin = max(4, self._zoom // 2 + 2)
        return QRect(
            pos.x() - radius - margin,
            pos.y() - radius - margin,
            radius * 2 + margin * 2 + 1,
            radius * 2 + margin * 2 + 1,
        ).intersected(self.rect())

    def _update_brush_cursor(self, pos: QPoint) -> None:
        dirty = self._cursor_dirty_rect(self._last_cursor_pos).united(self._cursor_dirty_rect(pos))
        self._last_cursor_pos = QPoint(pos)
        if not dirty.isEmpty():
            self.update(dirty)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        dirty = event.rect().intersected(self.rect())
        painter.fillRect(dirty, QColor(40, 42, 48))
        if self._qimage is not None:
            # Qt clips the scaled draw to the dirty region. No NumPy→QImage full copy is
            # performed here; the QImage references the persistent preview buffer.
            painter.drawImage(self.rect(), self._qimage)
            if self._show_grid:
                pen = QPen(QColor(255, 255, 255, 28))
                painter.setPen(pen)
                start_x = max(0, (dirty.left() // self._zoom) * self._zoom)
                start_y = max(0, (dirty.top() // self._zoom) * self._zoom)
                for x in range(start_x, dirty.right() + self._zoom + 1, self._zoom):
                    painter.drawLine(x, dirty.top(), x, dirty.bottom())
                for y in range(start_y, dirty.bottom() + self._zoom + 1, self._zoom):
                    painter.drawLine(dirty.left(), y, dirty.right(), y)

        self._paint_selection_overlay(painter)

        if self._tool_mode == 'brush':
            brush_pen = QPen(QColor(255, 180, 70, 210))
            brush_pen.setWidth(max(1, self._zoom // 4))
            painter.setPen(brush_pen)
            if self.hasMouseTracking():
                pos = self.mapFromGlobal(self.cursor().pos())
                if self.rect().contains(pos):
                    radius = self._brush_radius * self._zoom
                    painter.drawEllipse(pos, radius, radius)

    def _paint_selection_overlay(self, painter: QPainter) -> None:
        fill = QColor(80, 170, 255, 65)
        outline = QPen(QColor(90, 190, 255, 235))
        outline.setWidth(max(1, self._zoom // 5))
        painter.setPen(outline)
        painter.setBrush(fill)

        points = self._selection_points
        if self._selection_kind == 'rectangle' and len(points) == 2:
            p0 = self._screen_point(points[0])
            p1 = self._screen_point(points[1])
            painter.drawRect(QRectF(p0, p1).normalized())
        elif self._selection_kind == 'polygon' and len(points) >= 3:
            path = QPainterPath(self._screen_point(points[0]))
            for point in points[1:]:
                path.lineTo(self._screen_point(point))
            path.closeSubpath()
            painter.drawPath(path)

        painter.setBrush(QColor(80, 170, 255, 35))
        if self._tool_mode == 'rectangle' and self._rect_start is not None and self._rect_end is not None:
            painter.drawRect(QRectF(self._screen_point(self._rect_start), self._screen_point(self._rect_end)).normalized())
        elif self._tool_mode == 'polygon' and self._polygon_points:
            path = QPainterPath(self._screen_point(self._polygon_points[0]))
            for point in self._polygon_points[1:]:
                path.lineTo(self._screen_point(point))
            if self._polygon_hover is not None:
                path.lineTo(self._screen_point(self._polygon_hover))
            painter.drawPath(path)
            painter.setBrush(QColor(90, 190, 255, 235))
            for point in self._polygon_points:
                screen = self._screen_point(point)
                radius = max(2, self._zoom // 3)
                painter.drawEllipse(screen, radius, radius)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        source = self._source_point(event)
        if source is None:
            return
        if self._tool_mode == 'brush':
            self._painting = True
            self.brush_stroke_started.emit(float(source[0]), float(source[1]))
        elif self._tool_mode == 'rectangle':
            self._rect_start = source
            self._rect_end = source
            self._selection_kind = None
            self._selection_points = []
        elif self._tool_mode == 'polygon':
            self._selection_kind = None
            self._selection_points = []
            if not self._polygon_points or self._distance_sq(self._polygon_points[-1], source) > 0.04:
                self._polygon_points.append(source)
            self._polygon_hover = source
        if self._tool_mode == 'brush':
            self._update_brush_cursor(event.position().toPoint())
        else:
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        source = self._source_point(event)
        if source is None:
            return
        if self._tool_mode == 'brush':
            if self._painting:
                self.brush_painted.emit(float(source[0]), float(source[1]))
            self._update_brush_cursor(event.position().toPoint())
            return
        if self._tool_mode == 'rectangle' and self._rect_start is not None:
            self._rect_end = source
        elif self._tool_mode == 'polygon' and self._polygon_points:
            self._polygon_hover = source
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._tool_mode == 'brush':
            if self._painting:
                self._painting = False
                self.brush_stroke_finished.emit()
            self._update_brush_cursor(event.position().toPoint())
            return
        if self._tool_mode == 'rectangle' and self._rect_start is not None:
            source = self._source_point(event)
            if source is not None:
                self._rect_end = source
                self._selection_kind = 'rectangle'
                self._selection_points = [self._rect_start, self._rect_end]
                self.rectangle_selected.emit(
                    float(self._rect_start[0]),
                    float(self._rect_start[1]),
                    float(self._rect_end[0]),
                    float(self._rect_end[1]),
                )
            self._rect_start = None
            self._rect_end = None
        self.update()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        dirty = self._cursor_dirty_rect(self._last_cursor_pos)
        self._last_cursor_pos = None
        if not dirty.isEmpty():
            self.update(dirty)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._tool_mode != 'polygon' or event.button() != Qt.MouseButton.LeftButton:
            return
        source = self._source_point(event)
        if source is not None and (not self._polygon_points or self._distance_sq(self._polygon_points[-1], source) > 0.04):
            self._polygon_points.append(source)
        self._finish_polygon()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._tool_mode == 'polygon':
            self._finish_polygon()
            event.accept()
            return
        super().keyPressEvent(event)

    def _finish_polygon(self) -> None:
        if len(self._polygon_points) < 3:
            return
        points = list(self._polygon_points)
        self._selection_kind = 'polygon'
        self._selection_points = points
        self._polygon_points = []
        self._polygon_hover = None
        self.polygon_selected.emit(points)
        self.update()

    @staticmethod
    def _distance_sq(a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
