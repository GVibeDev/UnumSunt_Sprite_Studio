from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class PreviewLabel(QLabel):
    image_clicked = Signal(int, int)

    def __init__(self, *, clickable: bool = False) -> None:
        super().__init__()
        self._source_width = 0
        self._source_height = 0
        self._original_pixmap: QPixmap | None = None
        self._clickable = clickable

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(360, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "QLabel { background: #17191d; border: 1px solid #383c44; color: #c9cdd5; }"
        )
        self.setText("Nessun video caricato")

    def set_preview_pixmap(
        self,
        pixmap: QPixmap,
        source_width: int,
        source_height: int,
    ) -> None:
        self._original_pixmap = pixmap
        self._source_width = source_width
        self._source_height = source_height
        self._refresh_scaled_pixmap()

    def clear_preview(self, text: str = "Nessun video caricato") -> None:
        self._original_pixmap = None
        self._source_width = 0
        self._source_height = 0
        self.clear()
        self.setText(text)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_scaled_pixmap()

    def _refresh_scaled_pixmap(self) -> None:
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return
        scaled = self._original_pixmap.scaled(
            max(1, self.width() - 8),
            max(1, self.height() - 8),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        if (
            not self._clickable
            or self.pixmap() is None
            or self._source_width <= 0
            or self._source_height <= 0
        ):
            return

        pixmap = self.pixmap()
        if pixmap is None:
            return

        displayed_width = pixmap.width()
        displayed_height = pixmap.height()
        left = (self.width() - displayed_width) / 2.0
        top = (self.height() - displayed_height) / 2.0
        x = event.position().x() - left
        y = event.position().y() - top

        if x < 0 or y < 0 or x >= displayed_width or y >= displayed_height:
            return

        source_x = min(
            self._source_width - 1,
            max(0, int(x * self._source_width / displayed_width)),
        )
        source_y = min(
            self._source_height - 1,
            max(0, int(y * self._source_height / displayed_height)),
        )
        self.image_clicked.emit(source_x, source_y)
