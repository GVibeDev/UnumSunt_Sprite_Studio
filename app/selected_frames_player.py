from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.chroma_key import apply_chroma_key, render_checkerboard
from app.models import ChromaKeySettings
from app.preview_label import PreviewLabel


class SelectedFramesPlayer(QWidget):
    frame_requested = Signal(int)
    status_message = Signal(str)

    def __init__(
        self,
        *,
        frame_loader: Callable[[int], np.ndarray],
        chroma_provider: Callable[[], ChromaKeySettings],
        rgba_override_provider: Callable[[int], np.ndarray | None] | None = None,
    ) -> None:
        super().__init__()
        self._frame_loader = frame_loader
        self._chroma_provider = chroma_provider
        self._rgba_override_provider = rgba_override_provider
        self._r1_indices: list[int] = []
        self._r3_indices: list[int] = []
        self._position = 0
        self._cache: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._cache_limit = 96

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance)

        self._build_ui()
        self._refresh_controls()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Sequence"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(
            [
                'R3 checked frames',
                'Manual R1 Selection',
            ]
        )
        self.source_combo.currentIndexChanged.connect(
            self._on_source_changed
        )
        source_row.addWidget(self.source_combo, 1)
        layout.addLayout(source_row)

        self.preview = PreviewLabel()
        self.preview.setMinimumSize(460, 460)
        layout.addWidget(self.preview, 1)

        transport = QHBoxLayout()
        self.previous_button = QPushButton("⏮")
        self.previous_button.setToolTip('Previous frame')
        self.previous_button.clicked.connect(self.previous_frame)
        self.play_button = QPushButton("▶ Play")
        self.play_button.clicked.connect(self.toggle_playback)
        self.next_button = QPushButton("⏭")
        self.next_button.setToolTip('Next Frame')
        self.next_button.clicked.connect(self.next_frame)
        self.loop_checkbox = QCheckBox("Loop")
        self.loop_checkbox.setChecked(True)

        transport.addWidget(self.previous_button)
        transport.addWidget(self.play_button)
        transport.addWidget(self.next_button)
        transport.addStretch(1)
        transport.addWidget(self.loop_checkbox)
        layout.addLayout(transport)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel('Speed'))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 30)
        self.speed_slider.setValue(10)
        self.speed_slider.valueChanged.connect(
            self._on_speed_changed
        )
        self.speed_label = QLabel("10 FPS")
        self.speed_label.setMinimumWidth(58)
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_label)
        layout.addLayout(speed_row)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.valueChanged.connect(
            self._set_position
        )
        layout.addWidget(self.position_slider)

        self.frame_label = QLabel('No frames in sequence')
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.frame_label)

    def set_r1_indices(self, indices: list[int]) -> None:
        self._r1_indices = sorted(set(int(index) for index in indices))
        if self.source_combo.currentIndex() == 1:
            self._reset_position_preserving_frame()

    def set_r3_indices(self, indices: list[int]) -> None:
        self._r3_indices = sorted(set(int(index) for index in indices))
        if self.source_combo.currentIndex() == 0:
            self._reset_position_preserving_frame()

    def invalidate_cache(self) -> None:
        self._cache.clear()
        self._show_current()

    def clear(self) -> None:
        self.stop()
        self._r1_indices.clear()
        self._r3_indices.clear()
        self._cache.clear()
        self._position = 0
        self.preview.clear_preview('No video loaded')
        self.frame_label.setText('No frames in sequence')
        self._refresh_controls()

    def current_indices(self) -> list[int]:
        return (
            self._r3_indices
            if self.source_combo.currentIndex() == 0
            else self._r1_indices
        )

    def current_frame_index(self) -> Optional[int]:
        indices = self.current_indices()
        if not indices:
            return None
        self._position = min(max(self._position, 0), len(indices) - 1)
        return indices[self._position]

    def show_frame_index(self, frame_index: int) -> None:
        indices = self.current_indices()
        if frame_index in indices:
            self._set_position(indices.index(frame_index))
            return

        alternate = self._r1_indices if self.source_combo.currentIndex() == 0 else self._r3_indices
        if frame_index in alternate:
            self.source_combo.setCurrentIndex(
                1 if self.source_combo.currentIndex() == 0 else 0
            )
            indices = self.current_indices()
            self._set_position(indices.index(frame_index))

    def preview_frame(self, frame_index: int) -> None:
        """Show any analyzed frame without changing the active sequence."""
        self.stop()
        try:
            preview_rgb = self._load_preview(int(frame_index))
        except Exception as exc:
            self.preview.clear_preview('Preview Error')
            self.frame_label.setText(f'Frame Error {frame_index}: {exc}')
            self.status_message.emit(str(exc))
            return
        self.preview.set_preview_pixmap(
            self._rgb_to_pixmap(preview_rgb),
            preview_rgb.shape[1],
            preview_rgb.shape[0],
        )
        self.frame_label.setText(f'Frame {int(frame_index)} · single preview')
        self.frame_requested.emit(int(frame_index))

    def toggle_playback(self) -> None:
        if self.timer.isActive():
            self.stop()
            return
        if not self.current_indices():
            return
        self.timer.start(self._interval_ms())
        self.play_button.setText("■ Pause")

    def stop(self) -> None:
        self.timer.stop()
        self.play_button.setText("▶ Play")

    def previous_frame(self) -> None:
        indices = self.current_indices()
        if not indices:
            return
        self._set_position((self._position - 1) % len(indices))

    def next_frame(self) -> None:
        indices = self.current_indices()
        if not indices:
            return
        next_position = self._position + 1
        if next_position >= len(indices):
            if not self.loop_checkbox.isChecked():
                self.stop()
                next_position = len(indices) - 1
            else:
                next_position = 0
        self._set_position(next_position)

    def _advance(self) -> None:
        self.next_frame()

    def _on_source_changed(self) -> None:
        self.stop()
        self._position = 0
        self._refresh_controls()
        self._show_current()

    def _on_speed_changed(self, fps: int) -> None:
        self.speed_label.setText(f"{fps} FPS")
        if self.timer.isActive():
            self.timer.start(self._interval_ms())

    def _interval_ms(self) -> int:
        return max(1, int(round(1000.0 / self.speed_slider.value())))

    def _set_position(self, position: int) -> None:
        indices = self.current_indices()
        if not indices:
            self._position = 0
            self._refresh_controls()
            return
        self._position = min(max(int(position), 0), len(indices) - 1)
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(self._position)
        self.position_slider.blockSignals(False)
        self._show_current()

    def _reset_position_preserving_frame(self) -> None:
        previous_frame = self.current_frame_index()
        indices = self.current_indices()
        if previous_frame in indices:
            self._position = indices.index(previous_frame)
        else:
            self._position = 0
        self._refresh_controls()
        self._show_current()

    def _refresh_controls(self) -> None:
        indices = self.current_indices()
        enabled = bool(indices)
        self.previous_button.setEnabled(enabled)
        self.play_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)
        self.position_slider.setEnabled(enabled)
        self.position_slider.setRange(0, max(0, len(indices) - 1))
        if not enabled:
            self.stop()
            self.position_slider.setValue(0)

    def _show_current(self) -> None:
        self._refresh_controls()
        frame_index = self.current_frame_index()
        if frame_index is None:
            self.preview.clear_preview('No frames in sequence')
            self.frame_label.setText('No frames in sequence')
            return

        try:
            preview_rgb = self._load_preview(frame_index)
        except Exception as exc:
            self.stop()
            self.preview.clear_preview('Preview Error')
            self.frame_label.setText(f'Frame Error {frame_index}: {exc}')
            self.status_message.emit(str(exc))
            return

        self.preview.set_preview_pixmap(
            self._rgb_to_pixmap(preview_rgb),
            preview_rgb.shape[1],
            preview_rgb.shape[0],
        )
        indices = self.current_indices()
        self.frame_label.setText(
            f"Frame {frame_index} · {self._position + 1}/{len(indices)} · "
            f"{self.speed_slider.value()} FPS"
        )
        if not self.timer.isActive():
            self.frame_requested.emit(frame_index)

    def _load_preview(self, frame_index: int) -> np.ndarray:
        settings = self._chroma_provider()
        cache_key = (
            frame_index,
            tuple(settings.background_rgb),
            settings.tolerance,
            settings.softness,
            settings.cleanup_radius,
            settings.edge_decontamination,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return cached.copy()

        override = self._rgba_override_provider(frame_index) if self._rgba_override_provider is not None else None
        if override is not None:
            rgba = override.copy()
        else:
            source_rgb = self._frame_loader(frame_index)
            rgba, _ = apply_chroma_key(source_rgb, settings)
        preview_rgb = render_checkerboard(
            rgba,
            tile_size=18,
            light=202,
            dark=158,
        )
        self._cache[cache_key] = preview_rgb
        self._cache.move_to_end(cache_key)
        while len(self._cache) > self._cache_limit:
            self._cache.popitem(last=False)
        return preview_rgb.copy()

    @staticmethod
    def _rgb_to_pixmap(image_rgb: np.ndarray) -> QPixmap:
        contiguous = np.ascontiguousarray(image_rgb)
        height, width, channels = contiguous.shape
        if channels != 3:
            raise ValueError('The preview requires an RGB image.')
        qimage = QImage(
            contiguous.data,
            width,
            height,
            contiguous.strides[0],
            QImage.Format.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(qimage)
