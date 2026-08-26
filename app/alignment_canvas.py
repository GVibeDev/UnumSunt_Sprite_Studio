from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class AlignmentCanvas(QWidget):
    canvas_clicked = Signal(float, float)
    drag_started = Signal()
    drag_delta = Signal(int, int)
    drag_finished = Signal()
    nudge_requested = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self._canvas_width = 96
        self._canvas_height = 96
        self._zoom = 6
        self._pivot_x = 48.0
        self._pivot_y = 88.0
        self._current_rgba: np.ndarray | None = None
        self._onion_rgba: np.ndarray | None = None
        self._onion_opacity = 0.30
        self._show_grid = True
        self._show_pivot = True
        self._show_ground = True
        self._pivot_edit_mode = False
        self._drag_origin: QPoint | None = None
        self._last_drag_cell = QPoint(0, 0)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._update_fixed_size()

    def sizeHint(self) -> QSize:
        return QSize(
            self._canvas_width * self._zoom,
            self._canvas_height * self._zoom,
        )

    def set_canvas_geometry(
        self,
        width: int,
        height: int,
        pivot_x: float,
        pivot_y: float,
    ) -> None:
        self._canvas_width = max(1, int(width))
        self._canvas_height = max(1, int(height))
        self._pivot_x = float(pivot_x)
        self._pivot_y = float(pivot_y)
        self._update_fixed_size()
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self._zoom = max(1, min(20, int(zoom)))
        self._update_fixed_size()
        self.update()

    def set_images(
        self,
        current_rgba: np.ndarray | None,
        onion_rgba: np.ndarray | None,
    ) -> None:
        self._current_rgba = (
            None if current_rgba is None else np.ascontiguousarray(current_rgba)
        )
        self._onion_rgba = (
            None if onion_rgba is None else np.ascontiguousarray(onion_rgba)
        )
        self.update()

    def set_onion_opacity(self, value: float) -> None:
        self._onion_opacity = max(0.0, min(1.0, float(value)))
        self.update()

    def set_overlays(
        self,
        *,
        show_grid: bool,
        show_pivot: bool,
        show_ground: bool,
    ) -> None:
        self._show_grid = bool(show_grid)
        self._show_pivot = bool(show_pivot)
        self._show_ground = bool(show_ground)
        self.update()

    def set_pivot_edit_mode(self, enabled: bool) -> None:
        self._pivot_edit_mode = bool(enabled)
        self.setCursor(
            Qt.CursorShape.CrossCursor
            if self._pivot_edit_mode
            else Qt.CursorShape.OpenHandCursor
        )

    def _update_fixed_size(self) -> None:
        self.setFixedSize(
            self._canvas_width * self._zoom,
            self._canvas_height * self._zoom,
        )
        self.updateGeometry()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        checker_size = max(1, 8 * self._zoom)
        light = QColor(70, 73, 79)
        dark = QColor(52, 55, 61)
        for y in range(0, self.height(), checker_size):
            for x in range(0, self.width(), checker_size):
                painter.fillRect(
                    x,
                    y,
                    checker_size,
                    checker_size,
                    light if ((x // checker_size + y // checker_size) % 2 == 0) else dark,
                )

        if self._onion_rgba is not None:
            painter.save()
            painter.setOpacity(self._onion_opacity)
            painter.drawImage(
                self.rect(),
                self._rgba_to_qimage(self._onion_rgba),
            )
            painter.restore()

        if self._current_rgba is not None:
            painter.drawImage(
                self.rect(),
                self._rgba_to_qimage(self._current_rgba),
            )

        if self._show_grid:
            grid_pen = QPen(QColor(255, 255, 255, 32))
            grid_pen.setWidth(1)
            painter.setPen(grid_pen)
            step = 8 * self._zoom
            for x in range(0, self.width() + 1, step):
                painter.drawLine(x, 0, x, self.height())
            for y in range(0, self.height() + 1, step):
                painter.drawLine(0, y, self.width(), y)

        pivot_px_x = int(round(self._pivot_x * self._zoom))
        pivot_px_y = int(round(self._pivot_y * self._zoom))

        if self._show_ground:
            ground_pen = QPen(QColor(240, 190, 80, 190))
            ground_pen.setWidth(max(1, self._zoom // 3))
            painter.setPen(ground_pen)
            painter.drawLine(0, pivot_px_y, self.width(), pivot_px_y)

        if self._show_pivot:
            pivot_pen = QPen(QColor(255, 80, 80, 230))
            pivot_pen.setWidth(max(1, self._zoom // 3))
            painter.setPen(pivot_pen)
            arm = 6 * self._zoom
            painter.drawLine(
                pivot_px_x - arm,
                pivot_px_y,
                pivot_px_x + arm,
                pivot_px_y,
            )
            painter.drawLine(
                pivot_px_x,
                pivot_px_y - arm,
                pivot_px_x,
                pivot_px_y + arm,
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        logical_x = event.position().x() / self._zoom
        logical_y = event.position().y() / self._zoom

        if self._pivot_edit_mode:
            self.canvas_clicked.emit(logical_x, logical_y)
            return

        self._drag_origin = event.position().toPoint()
        self._last_drag_cell = QPoint(0, 0)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.drag_started.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_origin is None:
            return
        delta = event.position().toPoint() - self._drag_origin
        cell_delta = QPoint(
            int(round(delta.x() / self._zoom)),
            int(round(delta.y() / self._zoom)),
        )
        if cell_delta != self._last_drag_cell:
            self._last_drag_cell = cell_delta
            self.drag_delta.emit(cell_delta.x(), cell_delta.y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_origin is not None:
            self._drag_origin = None
            self.drag_finished.emit()
        if not self._pivot_edit_mode:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        step = 5 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.nudge_requested.emit(-step, 0)
        elif key == Qt.Key.Key_Right:
            self.nudge_requested.emit(step, 0)
        elif key == Qt.Key.Key_Up:
            self.nudge_requested.emit(0, -step)
        elif key == Qt.Key.Key_Down:
            self.nudge_requested.emit(0, step)
        else:
            super().keyPressEvent(event)

    @staticmethod
    def _rgba_to_qimage(rgba: np.ndarray) -> QImage:
        if rgba.ndim != 3 or rgba.shape[2] != 4:
            raise ValueError('An RGBA image is required.')
        contiguous = np.ascontiguousarray(rgba)
        height, width, _ = contiguous.shape
        return QImage(
            contiguous.data,
            width,
            height,
            contiguous.strides[0],
            QImage.Format.Format_RGBA8888,
        ).copy()
