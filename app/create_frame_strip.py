from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.create_frame_context import CreateFrameContext, normalize_onion_skin_mode


class FrameStripModel(QAbstractListModel):
    """Virtualized frame-number model for the CREATE strip.

    P2-F intentionally avoids decoding thumbnails for every frame.  QListView
    virtualizes the visible cells while the validated VideoSource keeps ownership
    of decoding/caching.  Current and production-selected frames are rendered as
    lightweight text markers.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = CreateFrameContext()

    @property
    def context(self) -> CreateFrameContext:
        return self._context

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return self._context.frame_count

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid() or not 0 <= index.row() < self._context.frame_count:
            return None
        frame = index.row()
        if role == Qt.ItemDataRole.DisplayRole:
            current = frame == self._context.current_frame_index
            selected = frame in self._context.selected_frames
            if current and selected:
                prefix = '▶● '
            elif current:
                prefix = '▶ '
            elif selected:
                prefix = '● '
            else:
                prefix = ''
            digits = max(3, len(str(max(0, self._context.frame_count - 1))))
            return f'{prefix}{frame:0{digits}d}'
        if role == Qt.ItemDataRole.ToolTipRole:
            selected = frame in self._context.selected_frames
            seconds = self._context.frame_time_seconds(frame)
            timing = f' · {seconds:.3f}s' if seconds is not None else ''
            selection = ' · selected for production' if selected else ''
            return f'Frame {frame}{timing}{selection}'
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.UserRole:
            return frame
        return None

    def set_context(self, context: CreateFrameContext) -> None:
        if context == self._context:
            return
        old_count = self._context.frame_count
        if old_count != context.frame_count:
            self.beginResetModel()
            self._context = context
            self.endResetModel()
            return
        self._context = context
        if context.frame_count > 0:
            first = self.index(0, 0)
            last = self.index(context.frame_count - 1, 0)
            self.dataChanged.emit(
                first,
                last,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole],
            )


class CreateFrameStrip(QFrame):
    """Persistent current-frame / multi-selection control for CREATE."""

    frame_requested = Signal(int)
    selection_requested = Signal(object)
    onion_mode_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('createFrameStripFoundation')
        self.setProperty('workstationRole', 'createFrameStrip')
        self._context = CreateFrameContext()
        self._selection_anchor: int | None = None
        self._onion_mode = 'off'

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 5, 8, 5)
        root.setSpacing(4)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        title = QLabel('Frames', self)
        title.setObjectName('createFrameStripTitle')
        controls.addWidget(title)

        self.source_label = QLabel('Source: —', self)
        self.source_label.setObjectName('createFrameSourceLabel')
        controls.addWidget(self.source_label)
        controls.addStretch(1)

        self.previous_button = QToolButton(self)
        self.previous_button.setText('◀')
        self.previous_button.setToolTip('Previous frame')
        self.previous_button.clicked.connect(lambda: self._step_current(-1))
        controls.addWidget(self.previous_button)

        self.frame_spin = QSpinBox(self)
        self.frame_spin.setPrefix('Frame ')
        self.frame_spin.setRange(0, 0)
        self.frame_spin.setEnabled(False)
        self.frame_spin.valueChanged.connect(self._spin_requested)
        controls.addWidget(self.frame_spin)

        self.next_button = QToolButton(self)
        self.next_button.setText('▶')
        self.next_button.setToolTip('Next frame')
        self.next_button.clicked.connect(lambda: self._step_current(1))
        controls.addWidget(self.next_button)

        self.select_current_button = QToolButton(self)
        self.select_current_button.setText('+ Select')
        self.select_current_button.setToolTip('Add the current frame to the production selection')
        self.select_current_button.clicked.connect(self._select_current)
        controls.addWidget(self.select_current_button)

        self.deselect_current_button = QToolButton(self)
        self.deselect_current_button.setText('− Select')
        self.deselect_current_button.setToolTip('Remove the current frame from the production selection')
        self.deselect_current_button.clicked.connect(self._deselect_current)
        controls.addWidget(self.deselect_current_button)

        controls.addWidget(QLabel('Onion', self))
        self.onion_combo = QComboBox(self)
        self.onion_combo.addItem('Off', 'off')
        self.onion_combo.addItem('Previous', 'previous')
        self.onion_combo.addItem('Next', 'next')
        self.onion_combo.currentIndexChanged.connect(self._on_onion_combo_changed)
        controls.addWidget(self.onion_combo)

        self.frame_context_label = QLabel('Frame: —', self)
        self.frame_context_label.setObjectName('createFrameContextLabel')
        controls.addWidget(self.frame_context_label)
        root.addLayout(controls)

        self.model = FrameStripModel(self)
        self.view = QListView(self)
        self.view.setObjectName('createFrameStripView')
        self.view.setModel(self.model)
        self.view.setFlow(QListView.Flow.LeftToRight)
        self.view.setWrapping(False)
        self.view.setResizeMode(QListView.ResizeMode.Adjust)
        self.view.setMovement(QListView.Movement.Static)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.view.setUniformItemSizes(True)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setMinimumHeight(38)
        self.view.setMaximumHeight(58)
        self.view.clicked.connect(self._frame_clicked)
        root.addWidget(self.view)

        hint = QLabel('Click: current frame · Ctrl-click: toggle production selection · Shift-click: add range', self)
        hint.setObjectName('createFrameStripHint')
        hint.setProperty('workstationRole', 'createPanelHint')
        root.addWidget(hint)
        self.update_context(self._context)

    @property
    def context(self) -> CreateFrameContext:
        return self._context

    @property
    def onion_mode(self) -> str:
        return self._onion_mode

    def update_context(self, context: CreateFrameContext) -> None:
        self._context = context
        self.model.set_context(context)
        has_frames = context.has_frames
        current = context.current_frame_index
        self.source_label.setText(f'Source: {context.source_label or "—"}')
        self.source_label.setToolTip(context.source_kind or '')
        with QSignalBlocker(self.frame_spin):
            self.frame_spin.setEnabled(has_frames)
            self.frame_spin.setRange(0, max(0, context.frame_count - 1))
            self.frame_spin.setValue(current if current is not None else 0)
        self.previous_button.setEnabled(current is not None and current > 0)
        self.next_button.setEnabled(current is not None and current + 1 < context.frame_count)
        self.select_current_button.setEnabled(current is not None and current not in context.selected_frames)
        self.deselect_current_button.setEnabled(current is not None and current in context.selected_frames)

        if current is None:
            self.frame_context_label.setText('Frame: —')
        else:
            selected = context.selection_count
            seconds = context.frame_time_seconds(current)
            timing = f' · {seconds:.3f}s' if seconds is not None else ''
            self.frame_context_label.setText(
                f'Frame: {current} / {max(0, context.frame_count - 1)} · Selected: {selected}{timing}'
            )
            model_index = self.model.index(current, 0)
            if model_index.isValid():
                self.view.setCurrentIndex(model_index)
                self.view.scrollTo(model_index, QListView.ScrollHint.PositionAtCenter)

    def clear_context(self) -> None:
        self._selection_anchor = None
        self.update_context(CreateFrameContext())

    def set_onion_mode(self, mode: str, *, emit: bool = False) -> None:
        normalized = normalize_onion_skin_mode(mode)
        self._onion_mode = normalized
        target = self.onion_combo.findData(normalized)
        if target >= 0 and self.onion_combo.currentIndex() != target:
            with QSignalBlocker(self.onion_combo):
                self.onion_combo.setCurrentIndex(target)
        if emit:
            self.onion_mode_changed.emit(normalized)

    def _spin_requested(self, value: int) -> None:
        if self._context.has_frames:
            self.frame_requested.emit(int(value))

    def _step_current(self, delta: int) -> None:
        current = self._context.current_frame_index
        if current is None:
            return
        target = current + int(delta)
        if 0 <= target < self._context.frame_count:
            self.frame_requested.emit(target)

    def _frame_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        frame = int(index.row())
        self.frame_requested.emit(frame)
        modifiers = QApplication.keyboardModifiers()
        selected = set(self._context.selected_frames)
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if frame in selected:
                selected.remove(frame)
            else:
                selected.add(frame)
            self._selection_anchor = frame
            self.selection_requested.emit(tuple(sorted(selected)))
            return
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            anchor = self._selection_anchor
            if anchor is None:
                anchor = self._context.current_frame_index
            if anchor is None:
                anchor = frame
            first, last = sorted((int(anchor), frame))
            selected.update(range(first, last + 1))
            self.selection_requested.emit(tuple(sorted(selected)))
            return
        self._selection_anchor = frame

    def _select_current(self) -> None:
        current = self._context.current_frame_index
        if current is None:
            return
        selected = set(self._context.selected_frames)
        selected.add(current)
        self._selection_anchor = current
        self.selection_requested.emit(tuple(sorted(selected)))

    def _deselect_current(self) -> None:
        current = self._context.current_frame_index
        if current is None:
            return
        selected = set(self._context.selected_frames)
        selected.discard(current)
        self._selection_anchor = current
        self.selection_requested.emit(tuple(sorted(selected)))

    def _on_onion_combo_changed(self, _index: int) -> None:
        mode = normalize_onion_skin_mode(str(self.onion_combo.currentData() or 'off'))
        if mode == self._onion_mode:
            return
        self._onion_mode = mode
        self.onion_mode_changed.emit(mode)
