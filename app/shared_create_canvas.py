from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from app.canvas_input import (
    CanvasInputController,
    CanvasInputResult,
    CanvasPointerEvent,
    PointerButton,
    PointerPhase,
    ToolInputTarget,
)
from app.canvas_layers import (
    CanvasGuideState,
    CanvasImageLayerCache,
    CanvasRasterRole,
    CanvasSelectionRect,
)
from app.create_workspace_state import CreateWorkspaceState


class SharedCreateCanvas(QWidget):
    """Persistent CREATE production canvas.

    P2-C established pointer ownership and persistent view state. P2-E makes the
    same widget a real non-destructive renderer for the current RGBA frame plus
    overlay foundations. The layer cache is presentation-only: it never replaces
    ProjectStore, ProjectState, CleanupStudio edit buffers or Alignment state.
    """

    general_context_menu_requested = Signal(QPoint)
    view_transform_changed = Signal(float, float, float)
    input_mode_changed = Signal(str)
    layers_changed = Signal(int)
    source_files_dropped = Signal(object)

    _EMPTY_PLANE_SIZE = 512.0
    _CONTENT_MARGIN = 48.0

    def __init__(
        self,
        *,
        state: CreateWorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.input_controller = CanvasInputController()
        self.layers = CanvasImageLayerCache()
        self._route_label = '—'
        self._current_qimage: QImage | None = None
        self._onion_qimage: QImage | None = None
        self.setObjectName('sharedCreateCanvas')
        self.setProperty('workstationRole', 'sharedCreateCanvas')
        self.setMinimumSize(360, 280)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def input_mode(self) -> str:
        return self.input_controller.mode

    @property
    def has_image_layer(self) -> bool:
        return self._current_qimage is not None

    def set_route_context(self, route_label: str | None) -> None:
        self._route_label = str(route_label or '—')
        self.update()

    # ------------------------------------------------------------------
    # P2-E render-layer API
    # ------------------------------------------------------------------
    def set_frame_layers(
        self,
        current_rgba: np.ndarray | None,
        onion_rgba: np.ndarray | None = None,
    ) -> None:
        self.layers.set_images(current_rgba, onion_rgba)
        self._current_qimage = self._qimage_from_rgba(self.layers.current_view())
        self._onion_qimage = self._qimage_from_rgba(self.layers.onion_view())
        self._sync_visual_raster_metadata()
        self.layers_changed.emit(self.layers.revision)
        self.update()

    def set_onion_layer(self, onion_rgba: np.ndarray | None) -> None:
        self.layers.set_onion(onion_rgba)
        self._onion_qimage = self._qimage_from_rgba(self.layers.onion_view())
        self._sync_visual_raster_metadata()
        self.layers_changed.emit(self.layers.revision)
        self.update()

    def clear_frame_layers(self) -> None:
        before = self.layers.revision
        self.layers.clear_images()
        self._current_qimage = None
        self._onion_qimage = None
        self.state.visual.layers.remove('current-frame')
        self.state.visual.layers.remove('onion-frame')
        self.state.visual.clear_document_geometry()
        if self.layers.revision != before:
            self.layers_changed.emit(self.layers.revision)
        self.update()

    def set_selection_rect(self, selection: CanvasSelectionRect | None) -> None:
        before = self.layers.revision
        self.layers.set_selection(selection)
        if selection is None:
            self.state.visual.overlays.clear_selection()
        else:
            self.state.visual.overlays.set_selection_rect(
                selection.x,
                selection.y,
                selection.x + selection.width,
                selection.y + selection.height,
            )
        if self.layers.revision != before:
            self.layers_changed.emit(self.layers.revision)
        self.update()

    def set_guides(self, guides: CanvasGuideState) -> None:
        before = self.layers.revision
        self.layers.set_guides(guides)
        overlays = self.state.visual.overlays
        overlays.set_guides(
            vertical=guides.vertical,
            horizontal=guides.horizontal,
            ground_y=guides.ground_y,
        )
        overlays.set_pivot(guides.pivot)
        if self.layers.revision != before:
            self.layers_changed.emit(self.layers.revision)
        self.update()

    def set_onion_skin_enabled(self, enabled: bool) -> None:
        self.state.visual.overlays.onion_skin_enabled = bool(enabled)
        self._sync_visual_raster_metadata()
        self.update()

    def set_onion_skin_opacity(self, value: float) -> None:
        self.state.visual.overlays.set_onion_opacity(value)
        layer = self.state.visual.layers.get('onion-frame')
        if layer is not None:
            self.state.visual.layers.set_opacity(
                'onion-frame',
                self.state.visual.overlays.onion_skin_opacity,
            )
        self.update()

    def _sync_visual_raster_metadata(self) -> None:
        visual = self.state.visual
        current_shape = self.layers.current_shape
        if current_shape is None:
            visual.layers.remove('current-frame')
            visual.layers.remove('onion-frame')
            visual.clear_document_geometry()
            return

        width, height = current_shape
        visual.set_document_size(width, height)
        visual.layers.upsert('current-frame', CanvasRasterRole.CURRENT_FRAME)

        if self.layers.onion_view() is None:
            visual.layers.remove('onion-frame')
            return

        mode = visual.overlays.onion_skin_mode
        role = CanvasRasterRole.ONION_NEXT if mode == 'next' else CanvasRasterRole.ONION_PREVIOUS
        visual.layers.upsert(
            'onion-frame',
            role,
            visible=visual.overlays.onion_skin_enabled,
            opacity=visual.overlays.onion_skin_opacity,
        )

    def image_rect(self) -> QRectF | None:
        shape = self.layers.current_shape
        if shape is None:
            return None
        width, height = shape
        scale = self._display_scale(width, height)
        cx = self.width() / 2.0 + float(self.state.view.pan_x)
        cy = self.height() / 2.0 + float(self.state.view.pan_y)
        return QRectF(
            cx - (width * scale) / 2.0,
            cy - (height * scale) / 2.0,
            width * scale,
            height * scale,
        )

    def image_to_canvas(self, x: float, y: float) -> QPointF | None:
        rect = self.image_rect()
        shape = self.layers.current_shape
        if rect is None or shape is None:
            return None
        width, height = shape
        return QPointF(
            rect.left() + (float(x) / width) * rect.width(),
            rect.top() + (float(y) / height) * rect.height(),
        )

    def canvas_to_image(self, x: float, y: float) -> tuple[float, float] | None:
        rect = self.image_rect()
        shape = self.layers.current_shape
        if rect is None or shape is None or not rect.contains(QPointF(float(x), float(y))):
            return None
        width, height = shape
        image_x = ((float(x) - rect.left()) / rect.width()) * width
        image_y = ((float(y) - rect.top()) / rect.height()) * height
        return image_x, image_y

    # ------------------------------------------------------------------
    # Input contract from P2-C/P2-D
    # ------------------------------------------------------------------
    def activate_tool(self, tool_id: str, target: ToolInputTarget) -> None:
        self.input_controller.activate_tool(tool_id, target)
        self.state.tool.activate(tool_id)
        self.input_mode_changed.emit(self.input_controller.mode)
        self.update()

    def deactivate_tool(self) -> None:
        self.input_controller.deactivate_tool()
        self.state.tool.deactivate()
        self.input_mode_changed.emit(self.input_controller.mode)
        self.update()

    def cancel_pointer_interaction(self) -> None:
        self.input_controller.cancel_interaction()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        result = self.input_controller.dispatch(self._pointer_event(event, PointerPhase.PRESS))
        self._apply_input_result(result, event)
        if result.consumed:
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        result = self.input_controller.dispatch(self._pointer_event(event, PointerPhase.MOVE))
        self._apply_input_result(result, event)
        if result.consumed:
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        result = self.input_controller.dispatch(self._pointer_event(event, PointerPhase.RELEASE))
        self._apply_input_result(result, event)
        if result.consumed:
            event.accept()
        else:
            event.ignore()

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        # RMB is dispatched through CanvasInputController so Qt's additional
        # context-menu event must not open a second or accidental menu.
        event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        # P2-E connectivity closure: wheel zoom is a neutral canvas-view action.
        # While a tool is active we consume the event without neutral fallback;
        # tool-specific wheel semantics remain intentionally open.
        if self.state.tool.has_active_tool:
            event.accept()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        steps = float(delta) / 120.0
        old_zoom = max(0.05, float(self.state.view.zoom))
        new_zoom = min(32.0, max(0.10, old_zoom * (1.20 ** steps)))
        if abs(new_zoom - old_zoom) < 1e-9:
            event.accept()
            return

        cursor = event.position()
        old_center_x = self.width() / 2.0 + float(self.state.view.pan_x)
        old_center_y = self.height() / 2.0 + float(self.state.view.pan_y)
        factor = new_zoom / old_zoom
        new_center_x = float(cursor.x()) - (float(cursor.x()) - old_center_x) * factor
        new_center_y = float(cursor.y()) - (float(cursor.y()) - old_center_y) * factor
        new_pan_x = new_center_x - self.width() / 2.0
        new_pan_y = new_center_y - self.height() / 2.0
        self.state.view.set_view_transform(
            pan_x=new_pan_x,
            pan_y=new_pan_y,
            zoom=new_zoom,
        )
        self.view_transform_changed.emit(new_pan_x, new_pan_y, new_zoom)
        self.update()
        event.accept()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        mime = event.mimeData()
        if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if not paths:
            event.ignore()
            return
        self.cancel_pointer_interaction()
        self.source_files_dropped.emit(paths)
        event.acceptProposedAction()

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        self.cancel_pointer_interaction()
        super().focusOutEvent(event)

    def hideEvent(self, event) -> None:  # type: ignore[override]
        self.cancel_pointer_interaction()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(16, 19, 24))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        image_rect = self.image_rect()
        if image_rect is None or self._current_qimage is None:
            self._paint_empty_plane(painter)
        else:
            self._paint_image_layers(painter, image_rect)
            self._paint_overlays(painter, image_rect)

        painter.setPen(QColor(212, 218, 228))
        painter.drawText(16, 26, f'Shared CREATE Canvas · {self._route_label}')
        painter.setPen(QColor(139, 149, 164))
        tool_text = self.state.tool.active_tool_id or 'neutral'
        layer_text = 'RGBA frame' if self.has_image_layer else 'no frame'
        painter.drawText(
            16,
            47,
            f'Input: {tool_text} · {layer_text} · LMB-drag = Pan · wheel = Zoom · RMB = general menu · drop source files here',
        )
        painter.end()

    def _paint_empty_plane(self, painter: QPainter) -> None:
        zoom = max(0.05, float(self.state.view.zoom))
        plane_size = self._EMPTY_PLANE_SIZE * zoom
        cx = self.width() / 2.0 + float(self.state.view.pan_x)
        cy = self.height() / 2.0 + float(self.state.view.pan_y)
        plane = QRectF(cx - plane_size / 2.0, cy - plane_size / 2.0, plane_size, plane_size)

        painter.fillRect(plane, QColor(28, 32, 38))
        grid_step = max(8.0, 32.0 * zoom)
        grid_pen = QPen(QColor(50, 56, 66))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        x = plane.left()
        while x <= plane.right():
            painter.drawLine(int(x), int(plane.top()), int(x), int(plane.bottom()))
            x += grid_step
        y = plane.top()
        while y <= plane.bottom():
            painter.drawLine(int(plane.left()), int(y), int(plane.right()), int(y))
            y += grid_step
        painter.setPen(QPen(QColor(106, 116, 132), 1))
        painter.drawRect(plane)

    def _paint_image_layers(self, painter: QPainter, target: QRectF) -> None:
        if self.state.overlays.show_checkerboard:
            self._paint_checkerboard(painter, target)
        else:
            painter.fillRect(target, QColor(38, 42, 48))

        if (
            self.state.overlays.onion_skin_enabled
            and self._onion_qimage is not None
        ):
            painter.save()
            painter.setOpacity(float(self.state.overlays.onion_skin_opacity))
            painter.drawImage(target, self._onion_qimage)
            painter.restore()

        painter.drawImage(target, self._current_qimage)
        painter.setPen(QPen(QColor(112, 123, 140), 1))
        painter.drawRect(target)

    def _paint_checkerboard(self, painter: QPainter, target: QRectF) -> None:
        tile = 12
        light = QColor(66, 70, 76)
        dark = QColor(46, 50, 56)
        painter.save()
        painter.setClipRect(target)
        left = int(math.floor(target.left() / tile) * tile)
        top = int(math.floor(target.top() / tile) * tile)
        right = int(math.ceil(target.right()))
        bottom = int(math.ceil(target.bottom()))
        row = 0
        y = top
        while y < bottom:
            col = 0
            x = left
            while x < right:
                painter.fillRect(x, y, tile, tile, light if (row + col) % 2 == 0 else dark)
                x += tile
                col += 1
            y += tile
            row += 1
        painter.restore()

    def _paint_overlays(self, painter: QPainter, target: QRectF) -> None:
        shape = self.layers.current_shape
        if shape is None:
            return
        width, height = shape
        scale_x = target.width() / width
        scale_y = target.height() / height

        if self.state.overlays.show_pixel_grid and min(scale_x, scale_y) >= 6.0:
            painter.save()
            painter.setClipRect(target)
            painter.setPen(QPen(QColor(115, 125, 140, 90), 1))
            for x in range(1, width):
                sx = target.left() + x * scale_x
                if 0 <= sx <= self.width():
                    painter.drawLine(int(sx), int(target.top()), int(sx), int(target.bottom()))
            for y in range(1, height):
                sy = target.top() + y * scale_y
                if 0 <= sy <= self.height():
                    painter.drawLine(int(target.left()), int(sy), int(target.right()), int(sy))
            painter.restore()

        guides = self.layers.guides
        if self.state.overlays.show_guides:
            painter.save()
            painter.setClipRect(target)
            painter.setPen(QPen(QColor(84, 186, 220, 190), 1, Qt.PenStyle.DashLine))
            for value in guides.vertical:
                sx = target.left() + float(value) * scale_x
                painter.drawLine(int(sx), int(target.top()), int(sx), int(target.bottom()))
            for value in guides.horizontal:
                sy = target.top() + float(value) * scale_y
                painter.drawLine(int(target.left()), int(sy), int(target.right()), int(sy))
            painter.restore()

        if self.state.overlays.show_ground and guides.ground_y is not None:
            sy = target.top() + float(guides.ground_y) * scale_y
            painter.setPen(QPen(QColor(226, 170, 74, 220), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(target.left()), int(sy), int(target.right()), int(sy))

        if self.state.overlays.show_pivot and guides.pivot is not None:
            px = target.left() + guides.pivot[0] * scale_x
            py = target.top() + guides.pivot[1] * scale_y
            radius = 7
            painter.setPen(QPen(QColor(238, 99, 99, 235), 1))
            painter.drawLine(int(px - radius), int(py), int(px + radius), int(py))
            painter.drawLine(int(px), int(py - radius), int(px), int(py + radius))
            painter.drawEllipse(QPointF(px, py), 3.0, 3.0)

        selection = self.layers.selection
        if self.state.overlays.show_selection and selection is not None:
            rect = QRectF(
                target.left() + selection.x * scale_x,
                target.top() + selection.y * scale_y,
                selection.width * scale_x,
                selection.height * scale_y,
            )
            painter.setPen(QPen(QColor(244, 244, 244, 235), 1, Qt.PenStyle.DashLine))
            painter.drawRect(rect)

    def _display_scale(self, image_width: int, image_height: int) -> float:
        available_width = max(1.0, self.width() - self._CONTENT_MARGIN * 2.0)
        available_height = max(1.0, self.height() - self._CONTENT_MARGIN * 2.0 - 24.0)
        fit = min(available_width / image_width, available_height / image_height)
        # 1.0 means "fit current image". Persisted zoom remains a relative
        # multiplier, which keeps small sprites useful without inventing a fixed
        # pixel scale for every asset size.
        return max(0.02, fit * max(0.05, float(self.state.view.zoom)))

    @staticmethod
    def _qimage_from_rgba(image: np.ndarray | None) -> QImage | None:
        if image is None:
            return None
        contiguous = np.ascontiguousarray(image)
        height, width, channels = contiguous.shape
        if channels != 4:
            raise ValueError('Shared CREATE canvas requires RGBA image layers.')
        return QImage(
            contiguous.data,
            width,
            height,
            contiguous.strides[0],
            QImage.Format.Format_RGBA8888,
        ).copy()

    def _apply_input_result(self, result: CanvasInputResult, event: QMouseEvent) -> None:
        if result.pan_dx or result.pan_dy:
            view = self.state.view
            view.set_view_transform(
                pan_x=view.pan_x + result.pan_dx,
                pan_y=view.pan_y + result.pan_dy,
                zoom=view.zoom,
            )
            self.view_transform_changed.emit(view.pan_x, view.pan_y, view.zoom)
            self.update()
        if result.request_general_context_menu:
            self.general_context_menu_requested.emit(event.globalPosition().toPoint())

    @staticmethod
    def _pointer_event(event: QMouseEvent, phase: PointerPhase) -> CanvasPointerEvent:
        position = event.position()
        return CanvasPointerEvent(
            phase=phase,
            x=float(position.x()),
            y=float(position.y()),
            button=SharedCreateCanvas._button_from_qt(event.button()),
            buttons=frozenset(SharedCreateCanvas._buttons_from_qt(event.buttons())),
        )

    @staticmethod
    def _button_from_qt(button: Qt.MouseButton) -> PointerButton:
        if button == Qt.MouseButton.LeftButton:
            return PointerButton.LEFT
        if button == Qt.MouseButton.RightButton:
            return PointerButton.RIGHT
        if button == Qt.MouseButton.MiddleButton:
            return PointerButton.MIDDLE
        if button == Qt.MouseButton.NoButton:
            return PointerButton.NONE
        return PointerButton.OTHER

    @staticmethod
    def _buttons_from_qt(buttons: Qt.MouseButton) -> set[PointerButton]:
        result: set[PointerButton] = set()
        if buttons & Qt.MouseButton.LeftButton:
            result.add(PointerButton.LEFT)
        if buttons & Qt.MouseButton.RightButton:
            result.add(PointerButton.RIGHT)
        if buttons & Qt.MouseButton.MiddleButton:
            result.add(PointerButton.MIDDLE)
        return result
