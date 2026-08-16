from __future__ import annotations

from collections.abc import Callable
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.performance_probe import perf_instrument
from app.alpha_cleanup import (
    AlphaCleanupSettings,
    apply_alpha_cleanup,
    erase_alpha_selection,
    erase_alpha_selection_batch,
    paint_alpha_circle_inplace,
    polygon_selection_mask,
    rectangle_selection_mask,
    selection_mask_matches_rgba,
)
from app.chroma_key import apply_chroma_key, render_checkerboard, render_checkerboard_region
from app.cleanup_canvas import CleanupCanvas
from app.models import ChromaKeySettings, VideoMetadata
from app.video_source import VideoOpenError


class CleanupStudio(QWidget):
    frame_requested = Signal(int)
    status_message = Signal(str)
    overrides_changed = Signal()

    def __init__(
        self,
        *,
        frame_loader: Callable[[int], np.ndarray],
        metadata_provider: Callable[[], Optional[VideoMetadata]],
        chroma_provider: Callable[[], ChromaKeySettings],
        override_getter: Callable[[int], Optional[np.ndarray]],
        override_setter: Callable[[int, np.ndarray | None], None],
    ) -> None:
        super().__init__()
        self._frame_loader = frame_loader
        self._metadata_provider = metadata_provider
        self._chroma_provider = chroma_provider
        self._override_getter = override_getter
        self._override_setter = override_setter
        self._selected_indices: list[int] = []
        self._current_frame_index: int | None = None
        self._history: list[dict] = []
        self._history_redo: list[dict] = []
        self._cleanup_settings = AlphaCleanupSettings()
        self._selection_mask: np.ndarray | None = None
        self._selection_kind: str | None = None
        self._brush_stroke_frame: int | None = None
        self._brush_stroke_before: np.ndarray | None = None
        self._brush_stroke_working: np.ndarray | None = None
        self._brush_stroke_changed = False
        self._brush_stroke_dabs = 0
        self._build_ui()
        self._set_enabled(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self.info_label = QLabel('Seleziona frame in R1 per rifinire alpha e piccoli difetti.')
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 6px; background: #302a20; border: 1px solid #74643f; }')
        root.addWidget(self.info_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        self.canvas = CleanupCanvas()
        self.canvas.brush_stroke_started.connect(self._begin_brush_stroke)
        self.canvas.brush_painted.connect(self._paint_brush)
        self.canvas.brush_stroke_finished.connect(self._end_brush_stroke)
        self.canvas.rectangle_selected.connect(self._on_rectangle_selected)
        self.canvas.polygon_selected.connect(self._on_polygon_selected)
        self.canvas.selection_cancelled.connect(self._clear_selection_state)
        self.canvas.delete_requested.connect(self._delete_selection_current)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setMinimumSize(620, 560)
        left_layout.addWidget(scroll, 1)

        nav_row = QHBoxLayout()
        prev_button = QPushButton('◀ Frame precedente')
        prev_button.clicked.connect(lambda: self._select_relative(-1))
        next_button = QPushButton('Frame successivo ▶')
        next_button.clicked.connect(lambda: self._select_relative(1))
        self.current_label = QLabel('Nessun frame')
        self.current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(prev_button)
        nav_row.addWidget(self.current_label, 1)
        nav_row.addWidget(next_button)
        left_layout.addLayout(nav_row)

        self.frame_list = QListWidget()
        self.frame_list.setFlow(QListWidget.Flow.LeftToRight)
        self.frame_list.setWrapping(False)
        self.frame_list.setFixedHeight(72)
        self.frame_list.currentItemChanged.connect(self._on_frame_item_changed)
        left_layout.addWidget(self.frame_list)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        cleanup_group = QGroupBox('Clean-up alpha')
        cleanup_form = QFormLayout(cleanup_group)
        self.remove_islands_spin = QSpinBox(); self.remove_islands_spin.setRange(0, 512); self.remove_islands_spin.setValue(2)
        self.fill_holes_spin = QSpinBox(); self.fill_holes_spin.setRange(0, 512); self.fill_holes_spin.setValue(2)
        self.tighten_radius_spin = QSpinBox(); self.tighten_radius_spin.setRange(0, 6); self.tighten_radius_spin.setValue(0)
        cleanup_form.addRow('Rimuovi isole < px', self.remove_islands_spin)
        cleanup_form.addRow('Riempi buchi ≤ px', self.fill_holes_spin)
        cleanup_form.addRow('Stringi bordo', self.tighten_radius_spin)
        current_button = QPushButton('Applica clean-up al frame corrente')
        current_button.clicked.connect(self._apply_cleanup_current)
        selection_button = QPushButton('Applica clean-up ai frame selezionati')
        selection_button.clicked.connect(self._apply_cleanup_selected)
        cleanup_form.addRow('', current_button)
        cleanup_form.addRow('', selection_button)
        right_layout.addWidget(cleanup_group)

        paint_group = QGroupBox('Pixel painter')
        paint_form = QFormLayout(paint_group)
        self.brush_mode_combo = QComboBox(); self.brush_mode_combo.addItem('Cancella alpha', 'erase'); self.brush_mode_combo.addItem('Ripristina alpha', 'restore')
        self.brush_size_spin = QSpinBox(); self.brush_size_spin.setRange(1, 12); self.brush_size_spin.setValue(1)
        self.zoom_spin = QSpinBox(); self.zoom_spin.setRange(2, 24); self.zoom_spin.setValue(8)
        self.grid_checkbox = QCheckBox('Griglia pixel'); self.grid_checkbox.setChecked(True)
        self.alpha_only_checkbox = QCheckBox('Mostra alpha su scacchiera')
        undo_button = QPushButton('Annulla'); undo_button.clicked.connect(self._undo)
        redo_button = QPushButton('Ripeti'); redo_button.clicked.connect(self._redo)
        reset_button = QPushButton('Ripristina frame'); reset_button.clicked.connect(self._reset_current)
        paint_form.addRow('Modalità pennello', self.brush_mode_combo)
        paint_form.addRow('Raggio pennello', self.brush_size_spin)
        paint_form.addRow('Zoom', self.zoom_spin)
        paint_form.addRow('', self.grid_checkbox)
        paint_form.addRow('', self.alpha_only_checkbox)
        paint_form.addRow('', undo_button)
        paint_form.addRow('', redo_button)
        paint_form.addRow('', reset_button)
        right_layout.addWidget(paint_group)

        selection_group = QGroupBox('Selezioni e propagazione · R5e5-D')
        selection_form = QFormLayout(selection_group)
        self.tool_combo = QComboBox()
        self.tool_combo.addItem('Pennello', 'brush')
        self.tool_combo.addItem('Selezione rettangolare', 'rectangle')
        self.tool_combo.addItem('Lasso poligonale', 'polygon')
        self.selection_info_label = QLabel('Nessuna selezione')
        self.selection_info_label.setWordWrap(True)
        delete_selection_button = QPushButton('Cancella selezione (frame corrente)')
        delete_selection_button.clicked.connect(self._delete_selection_current)
        propagate_selection_button = QPushButton('Propaga ai frame selezionati')
        propagate_selection_button.clicked.connect(self._delete_selection_selected)
        clear_selection_button = QPushButton('Annulla selezione')
        clear_selection_button.clicked.connect(self._clear_selection)
        selection_form.addRow('Strumento', self.tool_combo)
        selection_form.addRow('Stato', self.selection_info_label)
        selection_form.addRow('', delete_selection_button)
        selection_form.addRow('', propagate_selection_button)
        selection_form.addRow('', clear_selection_button)
        selection_help = QLabel('Rettangolo: trascina. Lasso: click sui vertici, doppio click o Invio per chiudere. Del cancella il frame corrente; il pulsante di propagazione applica la stessa selezione a tutti i frame selezionati come singola transazione.')
        selection_help.setWordWrap(True)
        selection_help.setStyleSheet('color: #9198a5;')
        selection_form.addRow('', selection_help)
        right_layout.addWidget(selection_group)

        note = QLabel('Ritocco pensato per micro-difetti: residui di sfondo, buchi, pixel sporchi o piccoli inglobamenti.')
        note.setWordWrap(True)
        note.setStyleSheet('color: #9198a5;')
        right_layout.addWidget(note)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([940, 360])
        root.addWidget(splitter, 1)

        self.zoom_spin.valueChanged.connect(self.canvas.set_zoom)
        self.grid_checkbox.toggled.connect(self._update_canvas_overlays)
        self.alpha_only_checkbox.toggled.connect(self._refresh_current_preview)
        self.brush_size_spin.valueChanged.connect(self._update_canvas_overlays)
        self.tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        self.canvas.set_tool_mode(str(self.tool_combo.currentData()))

        self._delete_shortcut = QShortcut(QKeySequence('Delete'), self)
        self._delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._delete_shortcut.activated.connect(self._delete_selection_current)
        self._escape_shortcut = QShortcut(QKeySequence('Esc'), self)
        self._escape_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._escape_shortcut.activated.connect(self._clear_selection)
        self._undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self._undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._undo_shortcut.activated.connect(self._undo)
        self._redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self._redo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._redo_shortcut.activated.connect(self._redo)
        self._redo_alt_shortcut = QShortcut(QKeySequence('Ctrl+Shift+Z'), self)
        self._redo_alt_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._redo_alt_shortcut.activated.connect(self._redo)

    def reset_context_history(self) -> None:
        """Drop local undo/redo and transient selections when the active Project Group changes."""
        self._history.clear()
        self._history_redo.clear()
        self._clear_selection()

    def _set_enabled(self, enabled: bool) -> None:
        self.canvas.setEnabled(enabled)
        self.frame_list.setEnabled(enabled)

    def set_selected_frames(self, indices: list[int]) -> None:
        previous = self._current_frame_index
        metadata = self._metadata_provider()
        if metadata is None:
            normalized: list[int] = []
        else:
            normalized = sorted(
                set(
                    int(i)
                    for i in indices
                    if 0 <= int(i) < metadata.frame_count
                )
            )
        self._selected_indices = normalized
        self.frame_list.clear()
        for idx in self._selected_indices:
            item = QListWidgetItem(f'F{idx:06d}')
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.frame_list.addItem(item)
        enabled = bool(self._selected_indices) and metadata is not None
        self._set_enabled(enabled)
        if enabled:
            target = previous if previous in self._selected_indices else self._selected_indices[0]
            self._set_current_frame(target, emit_request=False)
            self.info_label.setText(f'{len(self._selected_indices)} frame disponibili per il clean-up.')
        else:
            self._show_missing_or_empty_source(missing_source=metadata is None)

    def _show_missing_or_empty_source(self, *, missing_source: bool) -> None:
        self._current_frame_index = None
        self._clear_selection()
        self.canvas.set_image(None)
        self.current_label.setText('Nessun frame')
        self._set_enabled(False)
        if missing_source:
            self.info_label.setText('Nessuna sorgente video aperta. Apri o importa una sorgente prima del clean-up.')
        else:
            self.info_label.setText('Seleziona frame in R1 per rifinire alpha e piccoli difetti.')

    def _selected_rgba(self, frame_index: int) -> np.ndarray:
        existing = self._override_getter(frame_index)
        if existing is not None:
            return existing.copy()
        source = self._frame_loader(frame_index)
        rgba, _ = apply_chroma_key(source, self._chroma_provider())
        return rgba

    def _preview_rgb(self, rgba: np.ndarray) -> np.ndarray:
        if self.alpha_only_checkbox.isChecked():
            return render_checkerboard(rgba, tile_size=12)
        return render_checkerboard(rgba, tile_size=14)

    def _capture_override_state(self, frame_index: int) -> np.ndarray | None:
        existing = self._override_getter(frame_index)
        return None if existing is None else existing.copy()

    def _apply_override_state(self, frame_index: int, rgba: np.ndarray | None) -> None:
        self._override_setter(frame_index, None if rgba is None else rgba.copy())

    def _push_transaction(
        self,
        *,
        label: str,
        before: dict[int, np.ndarray | None],
        after: dict[int, np.ndarray | None],
    ) -> None:
        transaction = {
            'label': label,
            'before': {int(k): (None if v is None else v.copy()) for k, v in before.items()},
            'after': {int(k): (None if v is None else v.copy()) for k, v in after.items()},
        }
        self._history.append(transaction)
        self._history_redo.clear()

    def _apply_transaction_state(self, state: dict[int, np.ndarray | None]) -> None:
        for frame_index, rgba in state.items():
            self._apply_override_state(int(frame_index), rgba)
        self.overrides_changed.emit()

    def _commit_transaction(
        self,
        *,
        label: str,
        before: dict[int, np.ndarray | None],
        after: dict[int, np.ndarray | None],
    ) -> None:
        self._apply_transaction_state(after)
        self._push_transaction(label=label, before=before, after=after)

    def _set_override(self, frame_index: int, rgba: np.ndarray | None) -> None:
        self._apply_override_state(frame_index, rgba)
        self.overrides_changed.emit()

    def _update_canvas_overlays(self) -> None:
        self.canvas.set_overlays(
            show_grid=self.grid_checkbox.isChecked(),
            show_alpha_only=self.alpha_only_checkbox.isChecked(),
            brush_radius=self.brush_size_spin.value(),
        )

    @perf_instrument('cleanup.refresh_current_preview')
    def _refresh_current_preview(self, *, emit_request: bool = True) -> None:
        if self._current_frame_index is None:
            return
        metadata = self._metadata_provider()
        if metadata is None or not (0 <= self._current_frame_index < metadata.frame_count):
            self._selected_indices = []
            self.frame_list.clear()
            self._show_missing_or_empty_source(missing_source=metadata is None)
            return
        try:
            rgba = self._selected_rgba(self._current_frame_index)
        except VideoOpenError:
            # The source can disappear between a Qt selection event and frame
            # decoding (project/group switch, close/reopen, shutdown). This is
            # a normal transient UI state, not an application crash.
            self._selected_indices = []
            self.frame_list.clear()
            self._show_missing_or_empty_source(missing_source=True)
            return
        self.canvas.set_image(self._preview_rgb(rgba))
        self._update_canvas_overlays()
        self.current_label.setText(f'Frame {self._current_frame_index}')
        if emit_request:
            self.frame_requested.emit(self._current_frame_index)

    def _set_current_frame(self, frame_index: int, *, emit_request: bool = True) -> None:
        if self._current_frame_index != frame_index:
            self._clear_selection()
        self._current_frame_index = frame_index
        for row in range(self.frame_list.count()):
            item = self.frame_list.item(row)
            if int(item.data(Qt.ItemDataRole.UserRole)) == frame_index:
                self.frame_list.blockSignals(True)
                self.frame_list.setCurrentItem(item)
                self.frame_list.blockSignals(False)
                break
        self._refresh_current_preview(emit_request=emit_request)

    def _on_frame_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        metadata = self._metadata_provider()
        if metadata is None:
            self.set_selected_frames([])
            return
        frame_index = int(current.data(Qt.ItemDataRole.UserRole))
        if not (0 <= frame_index < metadata.frame_count):
            self.set_selected_frames(self._selected_indices)
            return
        self._set_current_frame(frame_index)

    def _select_relative(self, delta: int) -> None:
        if not self._selected_indices or self._current_frame_index not in self._selected_indices:
            return
        pos = self._selected_indices.index(self._current_frame_index)
        self._set_current_frame(self._selected_indices[(pos + delta) % len(self._selected_indices)])

    def _on_tool_changed(self, *_args) -> None:
        mode = str(self.tool_combo.currentData())
        self.canvas.set_tool_mode(mode)
        if mode == 'brush':
            self.selection_info_label.setText('Pennello attivo')
        elif self._selection_mask is None:
            self.selection_info_label.setText('Nessuna selezione')

    def _selection_shape(self) -> tuple[int, int] | None:
        if self._current_frame_index is None:
            return None
        rgba = self._selected_rgba(self._current_frame_index)
        return int(rgba.shape[0]), int(rgba.shape[1])

    def _on_rectangle_selected(self, x0: float, y0: float, x1: float, y1: float) -> None:
        shape = self._selection_shape()
        if shape is None:
            return
        h, w = shape
        self._selection_mask = rectangle_selection_mask(h, w, x0, y0, x1, y1)
        self._selection_kind = 'rectangle'
        self.selection_info_label.setText(f'Rettangolo · {int(np.count_nonzero(self._selection_mask))} px selezionati')

    def _on_polygon_selected(self, points: object) -> None:
        shape = self._selection_shape()
        if shape is None:
            return
        normalized: list[tuple[float, float]] = []
        if isinstance(points, (list, tuple)):
            for point in points:
                if isinstance(point, (list, tuple)) and len(point) == 2:
                    normalized.append((float(point[0]), float(point[1])))
        if len(normalized) < 3:
            self._clear_selection()
            return
        h, w = shape
        self._selection_mask = polygon_selection_mask(h, w, normalized)
        self._selection_kind = 'polygon'
        self.selection_info_label.setText(f'Lasso poligonale · {int(np.count_nonzero(self._selection_mask))} px selezionati')

    def _clear_selection_state(self) -> None:
        self._selection_mask = None
        self._selection_kind = None
        if hasattr(self, 'selection_info_label'):
            if hasattr(self, 'tool_combo') and str(self.tool_combo.currentData()) == 'brush':
                self.selection_info_label.setText('Pennello attivo')
            else:
                self.selection_info_label.setText('Nessuna selezione')

    def _clear_selection(self) -> None:
        self._clear_selection_state()
        self.canvas.clear_selection(emit_signal=False)

    def _validated_selection_mask(self) -> np.ndarray | None:
        if self._selection_mask is None or not np.any(self._selection_mask):
            self.status_message.emit('Nessuna selezione valida da cancellare.')
            return None
        return self._selection_mask

    def _delete_selection_current(self) -> None:
        if self._current_frame_index is None:
            return
        selection = self._validated_selection_mask()
        if selection is None:
            return
        rgba = self._selected_rgba(self._current_frame_index)
        if not selection_mask_matches_rgba(rgba, selection):
            QMessageBox.warning(
                self,
                'Selezione incompatibile',
                'La selezione non coincide con le dimensioni del frame sorgente. Operazione annullata.',
            )
            self._clear_selection()
            return
        edited = erase_alpha_selection(rgba, selection)
        self._commit_transaction(
            label=f'cleanup_selection_current:{self._current_frame_index}',
            before={self._current_frame_index: self._capture_override_state(self._current_frame_index)},
            after={self._current_frame_index: edited},
        )
        selected_pixels = int(np.count_nonzero(selection))
        self._refresh_current_preview()
        self.status_message.emit(f'Cancellati {selected_pixels} pixel dalla selezione del frame {self._current_frame_index}.')

    def _delete_selection_selected(self) -> None:
        selection = self._validated_selection_mask()
        if selection is None:
            return
        if not self._selected_indices:
            return
        rgba_by_frame: dict[int, np.ndarray] = {}
        shapes: dict[int, tuple[int, int]] = {}
        for frame_index in self._selected_indices:
            rgba = self._selected_rgba(frame_index)
            rgba_by_frame[frame_index] = rgba
            shapes[frame_index] = rgba.shape[:2]
        unique_shapes = set(shapes.values())
        if len(unique_shapes) != 1 or selection.shape != next(iter(unique_shapes)):
            details = ', '.join(f'{idx}: {shape[1]}×{shape[0]}' for idx, shape in shapes.items())
            QMessageBox.warning(
                self,
                'Frame incompatibili',
                'La propagazione richiede che tutti i frame selezionati abbiano la stessa dimensione della selezione.\n\n' + details,
            )
            return
        edited_batch = erase_alpha_selection_batch(rgba_by_frame, selection)
        before = {frame_index: self._capture_override_state(frame_index) for frame_index in self._selected_indices}
        after = {frame_index: edited_batch[frame_index] for frame_index in self._selected_indices}
        self._commit_transaction(
            label=f'cleanup_selection_propagation:{len(self._selected_indices)}',
            before=before,
            after=after,
        )
        selected_pixels = int(np.count_nonzero(selection))
        self._refresh_current_preview()
        self.status_message.emit(
            f'Selezione propagata a {len(self._selected_indices)} frame come singola transazione ({selected_pixels} px per frame).',
        )

    def _cleanup_settings_current(self) -> AlphaCleanupSettings:
        return AlphaCleanupSettings(
            remove_islands_min_pixels=self.remove_islands_spin.value(),
            fill_holes_max_pixels=self.fill_holes_spin.value(),
            tighten_radius=self.tighten_radius_spin.value(),
            alpha_threshold=8,
        )

    def _apply_cleanup_to_frames(self, indices: list[int]) -> None:
        settings = self._cleanup_settings_current()
        before: dict[int, np.ndarray | None] = {}
        after: dict[int, np.ndarray | None] = {}
        for frame_index in indices:
            rgba = self._selected_rgba(frame_index)
            before[frame_index] = self._capture_override_state(frame_index)
            after[frame_index] = apply_alpha_cleanup(rgba, settings)
        self._commit_transaction(label=f'cleanup_auto:{len(indices)}', before=before, after=after)
        self._refresh_current_preview()
        self.status_message.emit(f'Clean-up applicato a {len(indices)} frame.')

    def _apply_cleanup_current(self) -> None:
        if self._current_frame_index is None:
            return
        self._apply_cleanup_to_frames([self._current_frame_index])

    def _apply_cleanup_selected(self) -> None:
        if not self._selected_indices:
            return
        self._apply_cleanup_to_frames(self._selected_indices)

    def _reset_brush_stroke_state(self) -> None:
        self._brush_stroke_frame = None
        self._brush_stroke_before = None
        self._brush_stroke_working = None
        self._brush_stroke_changed = False
        self._brush_stroke_dabs = 0

    def _begin_brush_stroke(self, x: float, y: float) -> None:
        """Start one non-destructive stroke and apply the initial dab.

        R5e13a committed one full override/history transaction for every mouse move.
        R5e13b snapshots once here and commits once in ``_end_brush_stroke``.
        """
        if self._current_frame_index is None:
            self._reset_brush_stroke_state()
            return
        # Defensive close in case a platform delivers a new press without release.
        if self._brush_stroke_frame is not None:
            self._end_brush_stroke()
        frame_index = int(self._current_frame_index)
        self._brush_stroke_frame = frame_index
        self._brush_stroke_before = self._capture_override_state(frame_index)
        self._brush_stroke_working = self._selected_rgba(frame_index)
        self._brush_stroke_changed = False
        self._brush_stroke_dabs = 0
        self._paint_brush(x, y)

    @perf_instrument('cleanup.paint_brush_event')
    def _paint_brush(self, x: float, y: float) -> None:
        if self._current_frame_index is None:
            return
        if self._brush_stroke_frame is None or self._brush_stroke_working is None:
            # Backward-compatible defensive path for direct signal/test invocation.
            self._begin_brush_stroke(x, y)
            return
        if int(self._current_frame_index) != int(self._brush_stroke_frame):
            self._end_brush_stroke()
            return

        region = paint_alpha_circle_inplace(
            self._brush_stroke_working,
            x,
            y,
            self.brush_size_spin.value(),
            str(self.brush_mode_combo.currentData()),
        )
        self._brush_stroke_dabs += 1
        if not region.changed:
            return
        self._brush_stroke_changed = True

        rgba_roi = self._brush_stroke_working[region.top:region.bottom, region.left:region.right]
        tile_size = 12 if self.alpha_only_checkbox.isChecked() else 14
        preview_roi = render_checkerboard_region(
            rgba_roi,
            origin_x=region.left,
            origin_y=region.top,
            tile_size=tile_size,
        )
        self.canvas.update_image_region(preview_roi, region.left, region.top)

    @perf_instrument('cleanup.brush_stroke_commit')
    def _end_brush_stroke(self) -> None:
        frame_index = self._brush_stroke_frame
        working = self._brush_stroke_working
        before = self._brush_stroke_before
        changed = self._brush_stroke_changed
        dabs = self._brush_stroke_dabs
        self._reset_brush_stroke_state()
        if frame_index is None or working is None or not changed:
            return

        # One full-frame state transition and one undo item per physical stroke.
        self._commit_transaction(
            label=f'cleanup_brush_stroke:{frame_index}:{dabs}',
            before={frame_index: before},
            after={frame_index: working},
        )
        # The cleanup canvas is already current through ROI updates. The single
        # overrides_changed emission above refreshes dependent R1/R2/R3 previews once.
        self.current_label.setText(f'Frame {frame_index}')
        self.status_message.emit(f'Pennellata applicata al frame {frame_index} · {dabs} campioni · 1 transazione Undo.')

    def _undo(self) -> None:
        if not self._history:
            return
        transaction = self._history.pop()
        self._apply_transaction_state(transaction['before'])
        self._history_redo.append(transaction)
        self._refresh_current_preview()
        self.status_message.emit(f"Annullata transazione: {transaction['label']}")

    def _redo(self) -> None:
        if not self._history_redo:
            return
        transaction = self._history_redo.pop()
        self._apply_transaction_state(transaction['after'])
        self._history.append(transaction)
        self._refresh_current_preview()
        self.status_message.emit(f"Ripetuta transazione: {transaction['label']}")

    def _reset_current(self) -> None:
        if self._current_frame_index is None:
            return
        self._commit_transaction(
            label=f'cleanup_reset:{self._current_frame_index}',
            before={self._current_frame_index: self._capture_override_state(self._current_frame_index)},
            after={self._current_frame_index: None},
        )
        self._refresh_current_preview()
        self.status_message.emit('Frame corrente ripristinato al chroma key originale.')
