from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.alignment_canvas import AlignmentCanvas
from app.alignment_engine import (
    FramePlacement,
    SubjectFrame,
    calculate_shared_fit_scale,
    estimate_anchor_by_mode,
    prepare_subject_frame,
    prepare_subject_frame_from_rgba,
    render_aligned_frame,
)
from app.alignment_export import AlignmentExportError, export_aligned_animation
from app.models import AlignmentSettings, ChromaKeySettings, FrameAlignmentState, VideoMetadata
from app.profile_store import ProfilesStore
from app.output_geometry import (
    MAX_OUTPUT_DIMENSION,
    MIN_OUTPUT_DIMENSION,
    OUTPUT_SIZE_PRESETS,
    analyze_canvas_geometry,
    locked_size_from_height,
    locked_size_from_width,
    migrate_canvas_pivot,
    preset_by_key,
    preset_for_size,
)


class AlignmentStudio(QWidget):
    frame_requested = Signal(int)
    status_message = Signal(str)

    def __init__(
        self,
        *,
        frame_loader: Callable[[int], object],
        metadata_provider: Callable[[], Optional[VideoMetadata]],
        chroma_provider: Callable[[], ChromaKeySettings],
        rgba_override_provider: Callable[[int], object | None] | None = None,
    ) -> None:
        super().__init__()
        self._frame_loader = frame_loader
        self._metadata_provider = metadata_provider
        self._chroma_provider = chroma_provider
        self._rgba_override_provider = rgba_override_provider
        self.profile_store = ProfilesStore()
        self._selected_indices: list[int] = []
        self._subjects: dict[int, SubjectFrame] = {}
        self._states: dict[int, FrameAlignmentState] = {}
        self._pending_restored_states: dict[int, FrameAlignmentState] = {}
        self._current_frame_index: int | None = None
        self._current_placement: FramePlacement | None = None
        self._dirty = True
        self._drag_start_offset = (0, 0)
        self.settings = AlignmentSettings()
        self._geometry_update_in_progress = False
        self._last_canvas_size = (self.settings.canvas_width, self.settings.canvas_height)
        self._locked_aspect_ratio = self.settings.canvas_width / self.settings.canvas_height
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance_loop)
        self._build_ui()
        self._refresh_alignment_profiles_combo()
        self._load_last_used_alignment_profile()
        self._set_prepared_controls_enabled(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        top_row = QHBoxLayout()
        self.refresh_button = QPushButton('Aggiorna dai frame R1')
        self.refresh_button.clicked.connect(self.prepare_from_r1)
        self.auto_anchors_button = QPushButton('Stima tutte le ancore')
        self.auto_anchors_button.clicked.connect(self._estimate_all_anchors)
        self.fit_button = QPushButton('Adatta tutti alla tela')
        self.fit_button.clicked.connect(self._fit_all)
        self.reset_offsets_button = QPushButton('Azzera offset')
        self.reset_offsets_button.clicked.connect(self._reset_all_offsets)
        self.play_button = QPushButton('▶ Anteprima loop')
        self.play_button.clicked.connect(self._toggle_loop)
        for w in (self.refresh_button, self.auto_anchors_button, self.fit_button, self.reset_offsets_button):
            top_row.addWidget(w)
        top_row.addStretch(1)
        top_row.addWidget(self.play_button)
        root.addLayout(top_row)

        self.dirty_label = QLabel('R2 non preparata: seleziona i frame in R1 e premi “Aggiorna dai frame R1”.')
        self.dirty_label.setWordWrap(True)
        self.dirty_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 6px; background: #3b3020; border: 1px solid #7e6633; }')
        root.addWidget(self.dirty_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        self.canvas = AlignmentCanvas()
        self.canvas.drag_started.connect(self._on_drag_started)
        self.canvas.drag_delta.connect(self._on_drag_delta)
        self.canvas.nudge_requested.connect(self._nudge_current)
        self.canvas.canvas_clicked.connect(self._on_canvas_pivot_clicked)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setMinimumSize(620, 560)
        left_layout.addWidget(scroll, 1)
        nav_row = QHBoxLayout()
        previous_button = QPushButton('◀ Frame precedente')
        previous_button.clicked.connect(lambda: self._select_relative_frame(-1))
        next_button = QPushButton('Frame successivo ▶')
        next_button.clicked.connect(lambda: self._select_relative_frame(1))
        self.current_frame_label = QLabel('Nessun frame')
        self.current_frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(previous_button)
        nav_row.addWidget(self.current_frame_label, 1)
        nav_row.addWidget(next_button)
        left_layout.addLayout(nav_row)
        self.frame_list = QListWidget()
        self.frame_list.setFlow(QListWidget.Flow.LeftToRight)
        self.frame_list.setWrapping(False)
        self.frame_list.setFixedHeight(72)
        self.frame_list.currentItemChanged.connect(self._on_frame_item_changed)
        left_layout.addWidget(self.frame_list)
        splitter.addWidget(left)

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(4, 0, 0, 0)

        canvas_group = QGroupBox('Geometria output e ancora globale · R5e2')
        canvas_form = QFormLayout(canvas_group)
        self.output_size_preset_combo = QComboBox()
        for preset in OUTPUT_SIZE_PRESETS:
            self.output_size_preset_combo.addItem(preset.label, preset.key)
        default_preset_index = self.output_size_preset_combo.findData('square-96')
        self.output_size_preset_combo.setCurrentIndex(default_preset_index if default_preset_index >= 0 else 0)
        self.canvas_width_spin = QSpinBox(); self.canvas_width_spin.setRange(MIN_OUTPUT_DIMENSION, MAX_OUTPUT_DIMENSION); self.canvas_width_spin.setValue(96)
        self.canvas_height_spin = QSpinBox(); self.canvas_height_spin.setRange(MIN_OUTPUT_DIMENSION, MAX_OUTPUT_DIMENSION); self.canvas_height_spin.setValue(96)
        self.lock_aspect_checkbox = QCheckBox('Blocca rapporto larghezza / altezza')
        self.preserve_pivot_checkbox = QCheckBox('Riposiziona il pivot in proporzione al formato')
        self.preserve_pivot_checkbox.setChecked(True)
        self.auto_fit_resize_checkbox = QCheckBox('Adatta automaticamente la scala al cambio formato')
        self.auto_fit_resize_checkbox.setChecked(False)
        self.canvas_pivot_x_spin = QDoubleSpinBox(); self.canvas_pivot_x_spin.setRange(0, MAX_OUTPUT_DIMENSION); self.canvas_pivot_x_spin.setDecimals(2); self.canvas_pivot_x_spin.setValue(48)
        self.canvas_pivot_y_spin = QDoubleSpinBox(); self.canvas_pivot_y_spin.setRange(0, MAX_OUTPUT_DIMENSION); self.canvas_pivot_y_spin.setDecimals(2); self.canvas_pivot_y_spin.setValue(88)
        self.margin_spin = QSpinBox(); self.margin_spin.setRange(0, 64); self.margin_spin.setValue(4)
        self.scale_spin = QDoubleSpinBox(); self.scale_spin.setRange(0.005, 64.0); self.scale_spin.setDecimals(6); self.scale_spin.setSingleStep(0.01); self.scale_spin.setValue(1.0)
        self.anchor_mode_combo = QComboBox(); self.anchor_mode_combo.addItem('Punto a terra', 'ground'); self.anchor_mode_combo.addItem('Centro geometrico', 'centroid'); self.anchor_mode_combo.addItem('Zona superiore', 'upper_body')
        bottom_center_button = QPushButton('Ancora basso-centro')
        bottom_center_button.clicked.connect(self._set_bottom_center_pivot)
        fit_geometry_button = QPushButton('Applica formato e adatta tutti')
        fit_geometry_button.clicked.connect(self._apply_geometry_and_fit)
        pivot_buttons = QWidget()
        pivot_buttons_layout = QHBoxLayout(pivot_buttons)
        pivot_buttons_layout.setContentsMargins(0, 0, 0, 0)
        pivot_buttons_layout.addWidget(bottom_center_button)
        pivot_buttons_layout.addWidget(fit_geometry_button)
        self.geometry_contract_label = QLabel('Output 96 × 96 · quadrato · nessun frame preparato')
        self.geometry_contract_label.setWordWrap(True)
        self.geometry_contract_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #263238; border: 1px solid #607d8b; }')
        canvas_form.addRow('Preset output', self.output_size_preset_combo)
        canvas_form.addRow('Larghezza px', self.canvas_width_spin)
        canvas_form.addRow('Altezza px', self.canvas_height_spin)
        canvas_form.addRow('', self.lock_aspect_checkbox)
        canvas_form.addRow('', self.preserve_pivot_checkbox)
        canvas_form.addRow('', self.auto_fit_resize_checkbox)
        canvas_form.addRow('Ancora tela X', self.canvas_pivot_x_spin)
        canvas_form.addRow('Ancora tela Y', self.canvas_pivot_y_spin)
        canvas_form.addRow('Margine sicurezza', self.margin_spin)
        canvas_form.addRow('Scala condivisa', self.scale_spin)
        canvas_form.addRow('Modalità auto-ancora', self.anchor_mode_combo)
        canvas_form.addRow('', pivot_buttons)
        canvas_form.addRow('Diagnostica', self.geometry_contract_label)
        controls_layout.addWidget(canvas_group)

        profile_group = QGroupBox('Profili allineamento')
        profile_layout = QVBoxLayout(profile_group)
        self.alignment_profile_combo = QComboBox()
        profile_load_button = QPushButton('Carica profilo')
        profile_load_button.clicked.connect(self._load_selected_alignment_profile)
        profile_save_button = QPushButton('Salva profilo corrente')
        profile_save_button.clicked.connect(self._save_current_alignment_profile_as)
        profile_delete_button = QPushButton('Elimina profilo')
        profile_delete_button.clicked.connect(self._delete_selected_alignment_profile)
        profile_layout.addWidget(self.alignment_profile_combo)
        profile_layout.addWidget(profile_load_button)
        profile_layout.addWidget(profile_save_button)
        profile_layout.addWidget(profile_delete_button)
        controls_layout.addWidget(profile_group)

        frame_group = QGroupBox('Allineamento frame corrente')
        frame_form = QFormLayout(frame_group)
        self.source_pivot_x_spin = QDoubleSpinBox(); self.source_pivot_x_spin.setRange(-4096, 4096); self.source_pivot_x_spin.setDecimals(2)
        self.source_pivot_y_spin = QDoubleSpinBox(); self.source_pivot_y_spin.setRange(-4096, 4096); self.source_pivot_y_spin.setDecimals(2)
        self.offset_x_spin = QSpinBox(); self.offset_x_spin.setRange(-2048, 2048)
        self.offset_y_spin = QSpinBox(); self.offset_y_spin.setRange(-2048, 2048)
        pivot_button_row = QWidget()
        pivot_button_layout = QHBoxLayout(pivot_button_row)
        pivot_button_layout.setContentsMargins(0, 0, 0, 0)
        self.click_pivot_button = QPushButton('Clicca ancora')
        self.click_pivot_button.setCheckable(True)
        self.click_pivot_button.toggled.connect(self.canvas.set_pivot_edit_mode)
        auto_current_button = QPushButton('Stima')
        auto_current_button.clicked.connect(self._estimate_current_anchor)
        pivot_button_layout.addWidget(self.click_pivot_button)
        pivot_button_layout.addWidget(auto_current_button)
        nudge_widget = QWidget()
        nudge_layout = QHBoxLayout(nudge_widget)
        nudge_layout.setContentsMargins(0, 0, 0, 0)
        for label, dx, dy in (('←', -1, 0), ('↑', 0, -1), ('↓', 0, 1), ('→', 1, 0)):
            button = QPushButton(label)
            button.setFixedWidth(36)
            button.clicked.connect(lambda checked=False, x=dx, y=dy: self._nudge_current(x, y))
            nudge_layout.addWidget(button)
        frame_form.addRow('Ancora sorgente X', self.source_pivot_x_spin)
        frame_form.addRow('Ancora sorgente Y', self.source_pivot_y_spin)
        frame_form.addRow('Imposta ancora', pivot_button_row)
        frame_form.addRow('Offset X', self.offset_x_spin)
        frame_form.addRow('Offset Y', self.offset_y_spin)
        frame_form.addRow('Sposta', nudge_widget)
        controls_layout.addWidget(frame_group)

        view_group = QGroupBox('Vista e onion skin')
        view_form = QFormLayout(view_group)
        self.zoom_spin = QSpinBox(); self.zoom_spin.setRange(1, 16); self.zoom_spin.setValue(6)
        self.onion_checkbox = QCheckBox('Mostra frame precedente'); self.onion_checkbox.setChecked(True)
        self.onion_opacity_slider = QSlider(Qt.Orientation.Horizontal); self.onion_opacity_slider.setRange(0, 100); self.onion_opacity_slider.setValue(30)
        self.grid_checkbox = QCheckBox('Griglia 8 px'); self.grid_checkbox.setChecked(True)
        self.pivot_checkbox = QCheckBox('Croce ancora'); self.pivot_checkbox.setChecked(True)
        self.ground_checkbox = QCheckBox('Linea riferimento'); self.ground_checkbox.setChecked(True)
        view_form.addRow('Zoom', self.zoom_spin)
        view_form.addRow('', self.onion_checkbox)
        view_form.addRow('Opacità onion', self.onion_opacity_slider)
        view_form.addRow('', self.grid_checkbox)
        view_form.addRow('', self.pivot_checkbox)
        view_form.addRow('', self.ground_checkbox)
        controls_layout.addWidget(view_group)

        animation_group = QGroupBox('Animazione ed esportazione')
        animation_form = QFormLayout(animation_group)
        self.animation_name_edit = QLineEdit('walk')
        self.direction_combo = QComboBox(); self.direction_combo.addItems(['south-east','south','south-west','west','north-west','north','north-east','east'])
        self.fps_spin = QSpinBox(); self.fps_spin.setRange(1, 60); self.fps_spin.setValue(10)
        self.loop_checkbox = QCheckBox('Loop'); self.loop_checkbox.setChecked(True)
        self.export_format_combo = QComboBox(); self.export_format_combo.addItems(['PNG', 'WebP lossless'])
        self.sheet_layout_combo = QComboBox(); self.sheet_layout_combo.addItems(['Orizzontale', 'Griglia', 'Verticale'])
        self.sheet_columns_spin = QSpinBox(); self.sheet_columns_spin.setRange(1, 64); self.sheet_columns_spin.setValue(8)
        self.sheet_padding_spin = QSpinBox(); self.sheet_padding_spin.setRange(0, 64); self.sheet_padding_spin.setValue(0)
        self.mirror_export_combo = QComboBox(); self.mirror_export_combo.addItem('Nessuno', 'none'); self.mirror_export_combo.addItem('Genera direzione opposta a specchio', 'opposite-lateral')
        export_button = QPushButton('Esporta frame + sprite sheet')
        export_button.clicked.connect(self._export_animation)
        animation_form.addRow('Nome', self.animation_name_edit)
        animation_form.addRow('Direzione', self.direction_combo)
        animation_form.addRow('FPS', self.fps_spin)
        animation_form.addRow('', self.loop_checkbox)
        animation_form.addRow('Formato', self.export_format_combo)
        animation_form.addRow('Layout sheet', self.sheet_layout_combo)
        animation_form.addRow('Colonne griglia', self.sheet_columns_spin)
        animation_form.addRow('Spaziatura', self.sheet_padding_spin)
        animation_form.addRow('Mirror laterale', self.mirror_export_combo)
        animation_form.addRow('', export_button)
        controls_layout.addWidget(animation_group)
        controls_layout.addStretch(1)

        controls_scroll = QScrollArea()
        controls_scroll.setWidget(controls)
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setMinimumWidth(410)
        controls.setMinimumWidth(380)
        splitter.addWidget(controls_scroll)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([930, 430])
        root.addWidget(splitter, 1)

        self.output_size_preset_combo.currentIndexChanged.connect(self._on_output_preset_changed)
        self.canvas_width_spin.valueChanged.connect(self._on_canvas_width_changed)
        self.canvas_height_spin.valueChanged.connect(self._on_canvas_height_changed)
        self.lock_aspect_checkbox.toggled.connect(self._on_lock_aspect_toggled)
        self.preserve_pivot_checkbox.toggled.connect(self._on_profile_relevant_setting_changed)
        self.auto_fit_resize_checkbox.toggled.connect(self._on_profile_relevant_setting_changed)
        for control in (self.canvas_pivot_x_spin, self.canvas_pivot_y_spin, self.margin_spin, self.scale_spin):
            control.valueChanged.connect(self._on_global_settings_changed)
        self.anchor_mode_combo.currentIndexChanged.connect(self._on_profile_relevant_setting_changed)
        for control in (self.source_pivot_x_spin, self.source_pivot_y_spin, self.offset_x_spin, self.offset_y_spin):
            control.valueChanged.connect(self._on_current_state_changed)
        self.zoom_spin.valueChanged.connect(self._on_zoom_changed)
        self.onion_checkbox.toggled.connect(self._on_view_setting_changed)
        self.onion_opacity_slider.valueChanged.connect(self._on_onion_opacity_changed)
        for checkbox in (self.grid_checkbox, self.pivot_checkbox, self.ground_checkbox):
            checkbox.toggled.connect(self._on_view_setting_changed)
        self.fps_spin.valueChanged.connect(self._on_profile_relevant_setting_changed)
        self.loop_checkbox.toggled.connect(self._on_profile_relevant_setting_changed)
        self.animation_name_edit.textChanged.connect(self._on_profile_relevant_setting_changed)
        self.direction_combo.currentIndexChanged.connect(self._on_profile_relevant_setting_changed)
        self.export_format_combo.currentIndexChanged.connect(self._on_profile_relevant_setting_changed)
        self.sheet_layout_combo.currentIndexChanged.connect(self._on_profile_relevant_setting_changed)
        self.sheet_columns_spin.valueChanged.connect(self._on_profile_relevant_setting_changed)
        self.sheet_padding_spin.valueChanged.connect(self._on_profile_relevant_setting_changed)
        self.mirror_export_combo.currentIndexChanged.connect(self._on_profile_relevant_setting_changed)

    def _capture_alignment_profile_data(self) -> dict:
        return {
            'output_size_preset': str(self.output_size_preset_combo.currentData()),
            'lock_aspect_ratio': self.lock_aspect_checkbox.isChecked(),
            'preserve_pivot_proportion': self.preserve_pivot_checkbox.isChecked(),
            'auto_fit_on_resize': self.auto_fit_resize_checkbox.isChecked(),
            'canvas_width': self.canvas_width_spin.value(),
            'canvas_height': self.canvas_height_spin.value(),
            'canvas_pivot_x': self.canvas_pivot_x_spin.value(),
            'canvas_pivot_y': self.canvas_pivot_y_spin.value(),
            'margin': self.margin_spin.value(),
            'shared_scale': self.scale_spin.value(),
            'anchor_mode': str(self.anchor_mode_combo.currentData()),
            'zoom': self.zoom_spin.value(),
            'onion_enabled': self.onion_checkbox.isChecked(),
            'onion_opacity': self.onion_opacity_slider.value(),
            'show_grid': self.grid_checkbox.isChecked(),
            'show_pivot': self.pivot_checkbox.isChecked(),
            'show_ground': self.ground_checkbox.isChecked(),
            'animation_name': self.animation_name_edit.text().strip() or 'walk',
            'direction': self.direction_combo.currentText().strip() or 'south-east',
            'fps': self.fps_spin.value(),
            'loop': self.loop_checkbox.isChecked(),
            'export_format_index': self.export_format_combo.currentIndex(),
            'sheet_layout_index': self.sheet_layout_combo.currentIndex(),
            'sheet_columns': self.sheet_columns_spin.value(),
            'sheet_padding': self.sheet_padding_spin.value(),
            'mirror_export_mode': str(self.mirror_export_combo.currentData()),
        }

    def _apply_alignment_profile_data(self, data: dict, *, persist_last: bool = True) -> None:
        blockers = [
            QSignalBlocker(self.output_size_preset_combo),
            QSignalBlocker(self.lock_aspect_checkbox), QSignalBlocker(self.preserve_pivot_checkbox), QSignalBlocker(self.auto_fit_resize_checkbox),
            QSignalBlocker(self.canvas_width_spin), QSignalBlocker(self.canvas_height_spin),
            QSignalBlocker(self.canvas_pivot_x_spin), QSignalBlocker(self.canvas_pivot_y_spin),
            QSignalBlocker(self.margin_spin), QSignalBlocker(self.scale_spin),
            QSignalBlocker(self.anchor_mode_combo), QSignalBlocker(self.zoom_spin),
            QSignalBlocker(self.onion_checkbox), QSignalBlocker(self.onion_opacity_slider),
            QSignalBlocker(self.grid_checkbox), QSignalBlocker(self.pivot_checkbox), QSignalBlocker(self.ground_checkbox),
            QSignalBlocker(self.animation_name_edit), QSignalBlocker(self.direction_combo),
            QSignalBlocker(self.fps_spin), QSignalBlocker(self.loop_checkbox),
            QSignalBlocker(self.export_format_combo), QSignalBlocker(self.sheet_layout_combo),
            QSignalBlocker(self.sheet_columns_spin), QSignalBlocker(self.sheet_padding_spin), QSignalBlocker(self.mirror_export_combo),
        ]
        _ = blockers  # keep alive
        self.lock_aspect_checkbox.setChecked(bool(data.get('lock_aspect_ratio', self.lock_aspect_checkbox.isChecked())))
        self.preserve_pivot_checkbox.setChecked(bool(data.get('preserve_pivot_proportion', self.preserve_pivot_checkbox.isChecked())))
        self.auto_fit_resize_checkbox.setChecked(bool(data.get('auto_fit_on_resize', self.auto_fit_resize_checkbox.isChecked())))
        self.canvas_width_spin.setValue(int(data.get('canvas_width', self.canvas_width_spin.value())))
        self.canvas_height_spin.setValue(int(data.get('canvas_height', self.canvas_height_spin.value())))
        preset_key = str(data.get('output_size_preset', preset_for_size(self.canvas_width_spin.value(), self.canvas_height_spin.value()).key))
        preset_index = self.output_size_preset_combo.findData(preset_key)
        self.output_size_preset_combo.setCurrentIndex(preset_index if preset_index >= 0 else 0)
        self.canvas_pivot_x_spin.setValue(float(data.get('canvas_pivot_x', self.canvas_pivot_x_spin.value())))
        self.canvas_pivot_y_spin.setValue(float(data.get('canvas_pivot_y', self.canvas_pivot_y_spin.value())))
        self.margin_spin.setValue(int(data.get('margin', self.margin_spin.value())))
        self.scale_spin.setValue(float(data.get('shared_scale', self.scale_spin.value())))
        anchor_mode = str(data.get('anchor_mode', self.anchor_mode_combo.currentData()))
        idx = self.anchor_mode_combo.findData(anchor_mode)
        if idx >= 0:
            self.anchor_mode_combo.setCurrentIndex(idx)
        self.zoom_spin.setValue(int(data.get('zoom', self.zoom_spin.value())))
        self.onion_checkbox.setChecked(bool(data.get('onion_enabled', self.onion_checkbox.isChecked())))
        self.onion_opacity_slider.setValue(int(data.get('onion_opacity', self.onion_opacity_slider.value())))
        self.grid_checkbox.setChecked(bool(data.get('show_grid', self.grid_checkbox.isChecked())))
        self.pivot_checkbox.setChecked(bool(data.get('show_pivot', self.pivot_checkbox.isChecked())))
        self.ground_checkbox.setChecked(bool(data.get('show_ground', self.ground_checkbox.isChecked())))
        self.animation_name_edit.setText(str(data.get('animation_name', self.animation_name_edit.text())))
        direction = str(data.get('direction', self.direction_combo.currentText()))
        direction_idx = self.direction_combo.findText(direction)
        if direction_idx >= 0:
            self.direction_combo.setCurrentIndex(direction_idx)
        self.fps_spin.setValue(int(data.get('fps', self.fps_spin.value())))
        self.loop_checkbox.setChecked(bool(data.get('loop', self.loop_checkbox.isChecked())))
        self.export_format_combo.setCurrentIndex(int(data.get('export_format_index', self.export_format_combo.currentIndex())))
        self.sheet_layout_combo.setCurrentIndex(int(data.get('sheet_layout_index', self.sheet_layout_combo.currentIndex())))
        self.sheet_columns_spin.setValue(int(data.get('sheet_columns', self.sheet_columns_spin.value())))
        self.sheet_padding_spin.setValue(int(data.get('sheet_padding', self.sheet_padding_spin.value())))
        mirror_mode = str(data.get('mirror_export_mode', self.mirror_export_combo.currentData()))
        mirror_idx = self.mirror_export_combo.findData(mirror_mode)
        if mirror_idx >= 0:
            self.mirror_export_combo.setCurrentIndex(mirror_idx)
        self._last_canvas_size = (self.canvas_width_spin.value(), self.canvas_height_spin.value())
        self._locked_aspect_ratio = self.canvas_width_spin.value() / self.canvas_height_spin.value()
        self._on_global_settings_changed()
        self.canvas.set_zoom(self.zoom_spin.value())
        self.canvas.set_onion_opacity(self.onion_opacity_slider.value() / 100.0)
        self._update_overlays()
        self._restart_play_timer_if_needed()
        if persist_last:
            self._remember_current_alignment_settings()
        if self._selected_indices:
            self.mark_dirty('Profilo allineamento applicato. Aggiorna R2 dai frame R1.')

    def _refresh_alignment_profiles_combo(self, selected_name: str | None = None) -> None:
        names = self.profile_store.list_profiles('alignment')
        self.alignment_profile_combo.clear()
        self.alignment_profile_combo.addItems(names)
        if selected_name and selected_name in names:
            self.alignment_profile_combo.setCurrentText(selected_name)

    def _remember_current_alignment_settings(self) -> None:
        self.profile_store.set_last_used('alignment', self._capture_alignment_profile_data())

    def _load_last_used_alignment_profile(self) -> None:
        data = self.profile_store.get_last_used('alignment')
        if data is not None:
            self._apply_alignment_profile_data(data, persist_last=False)

    def _save_current_alignment_profile_as(self) -> None:
        name, ok = QInputDialog.getText(self, 'Salva profilo allineamento', 'Nome profilo:')
        if not ok:
            return
        normalized = name.strip()
        if not normalized:
            return
        self.profile_store.set_profile('alignment', normalized, self._capture_alignment_profile_data())
        self._refresh_alignment_profiles_combo(normalized)
        self.status_message.emit(f'Profilo allineamento salvato: {normalized}')

    def _load_selected_alignment_profile(self) -> None:
        name = self.alignment_profile_combo.currentText().strip()
        if not name:
            return
        data = self.profile_store.get_profile('alignment', name)
        if data is None:
            QMessageBox.information(self, 'Profilo non trovato', 'Il profilo selezionato non è disponibile.')
            self._refresh_alignment_profiles_combo()
            return
        self._apply_alignment_profile_data(data, persist_last=True)
        self.status_message.emit(f'Profilo allineamento caricato: {name}')

    def _delete_selected_alignment_profile(self) -> None:
        name = self.alignment_profile_combo.currentText().strip()
        if not name:
            return
        answer = QMessageBox.question(self, 'Elimina profilo', f'Eliminare il profilo "{name}"?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.profile_store.delete_profile('alignment', name)
        self._refresh_alignment_profiles_combo()
        self.status_message.emit(f'Profilo allineamento eliminato: {name}')

    def set_selected_frames(self, frame_indices: list[int]) -> None:
        normalized = sorted(set(int(index) for index in frame_indices))
        if normalized != self._selected_indices:
            self._selected_indices = normalized
            self.mark_dirty('La selezione R1 è cambiata. Premi “Aggiorna dai frame R1”.')

    def mark_dirty(self, message: str | None = None) -> None:
        self._dirty = True
        self._stop_loop()
        self.dirty_label.setText(message or 'Le impostazioni R1 o i profili sono cambiati. Aggiorna R2 prima di esportare.')
        self.dirty_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 6px; background: #3b3020; border: 1px solid #7e6633; }')

    def clear_project(self) -> None:
        self._stop_loop()
        self._selected_indices = []
        self._subjects.clear()
        self._states.clear()
        self._pending_restored_states.clear()
        self._current_frame_index = None
        self._current_placement = None
        self.frame_list.clear()
        self.canvas.set_images(None, None)
        self.current_frame_label.setText('Nessun frame')
        self._dirty = True
        self._set_prepared_controls_enabled(False)
        self.dirty_label.setText('R2 non preparata: seleziona i frame in R1 e premi “Aggiorna dai frame R1”.')
        self._update_geometry_contract()

    def ensure_prepared(self) -> None:
        if self._dirty and self._selected_indices:
            self.prepare_from_r1()

    def _subject_for_index(self, frame_index: int) -> SubjectFrame:
        override = self._rgba_override_provider(frame_index) if self._rgba_override_provider is not None else None
        if override is not None:
            return prepare_subject_frame_from_rgba(frame_index, override)
        source_rgb = self._frame_loader(frame_index)
        return prepare_subject_frame(frame_index, source_rgb, self._chroma_provider())

    def prepare_from_r1(self) -> None:
        metadata = self._metadata_provider()
        if metadata is None:
            QMessageBox.information(self, 'Nessun video', 'Aprire prima un video nella scheda Estrazione R1.')
            return
        if not self._selected_indices:
            QMessageBox.information(self, 'Nessun frame', 'Selezionare almeno un fotogramma nella scheda Estrazione R1.')
            return
        progress = QProgressDialog('Preparazione sagome per R2…', 'Annulla', 0, len(self._selected_indices), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        new_subjects: dict[int, SubjectFrame] = {}
        new_states: dict[int, FrameAlignmentState] = {}
        try:
            for position, frame_index in enumerate(self._selected_indices, start=1):
                if progress.wasCanceled():
                    return
                progress.setLabelText(f'Estrazione sagoma frame {frame_index} ({position}/{len(self._selected_indices)})')
                subject = self._subject_for_index(frame_index)
                new_subjects[frame_index] = subject
                anchor_x, anchor_y = estimate_anchor_by_mode(subject.rgba, str(self.anchor_mode_combo.currentData()))
                new_states[frame_index] = FrameAlignmentState(frame_index=frame_index, source_pivot_x=anchor_x, source_pivot_y=anchor_y, anchor_mode=str(self.anchor_mode_combo.currentData()))
                progress.setValue(position)
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, 'Errore preparazione R2', f'Impossibile preparare i frame:\n{exc}')
            return
        progress.close()
        self._subjects = new_subjects
        self._states = new_states
        if self._pending_restored_states:
            for frame_index, restored in self._pending_restored_states.items():
                if frame_index in self._states:
                    self._states[frame_index] = restored
            self._pending_restored_states.clear()
        self._sync_settings_from_controls()
        try:
            self.settings.shared_scale = calculate_shared_fit_scale(self._subjects, self._states, self.settings)
        except ValueError as exc:
            QMessageBox.critical(self, 'Errore scala', str(exc))
            return
        with QSignalBlocker(self.scale_spin):
            self.scale_spin.setValue(self.settings.shared_scale)
        self._remember_current_alignment_settings()
        self._dirty = False
        self.dirty_label.setText(f'R2 pronta: {len(self._selected_indices)} frame, tela {self.settings.canvas_width}×{self.settings.canvas_height}, scala condivisa {self.settings.shared_scale:.5f}.')
        self.dirty_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 6px; background: #20382a; border: 1px solid #3d7b55; }')
        self._populate_frame_list()
        self._set_prepared_controls_enabled(True)
        self._set_current_frame(self._selected_indices[0])
        self._update_geometry_contract()
        self.status_message.emit('R2 preparata dai fotogrammi selezionati.')

    def _populate_frame_list(self) -> None:
        self.frame_list.clear()
        for frame_index in self._selected_indices:
            item = QListWidgetItem(f'F{frame_index:06d}')
            item.setData(Qt.ItemDataRole.UserRole, frame_index)
            self.frame_list.addItem(item)

    def _set_prepared_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.auto_anchors_button, self.fit_button, self.reset_offsets_button, self.play_button, self.source_pivot_x_spin, self.source_pivot_y_spin, self.offset_x_spin, self.offset_y_spin, self.click_pivot_button):
            widget.setEnabled(enabled)

    def _on_frame_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self._set_current_frame(int(current.data(Qt.ItemDataRole.UserRole)))

    def _set_current_frame(self, frame_index: int) -> None:
        if frame_index not in self._states:
            return
        self._current_frame_index = frame_index
        state = self._states[frame_index]
        with QSignalBlocker(self.source_pivot_x_spin), QSignalBlocker(self.source_pivot_y_spin), QSignalBlocker(self.offset_x_spin), QSignalBlocker(self.offset_y_spin):
            self.source_pivot_x_spin.setValue(state.source_pivot_x)
            self.source_pivot_y_spin.setValue(state.source_pivot_y)
            self.offset_x_spin.setValue(state.offset_x)
            self.offset_y_spin.setValue(state.offset_y)
        for row in range(self.frame_list.count()):
            item = self.frame_list.item(row)
            if int(item.data(Qt.ItemDataRole.UserRole)) == frame_index:
                with QSignalBlocker(self.frame_list):
                    self.frame_list.setCurrentItem(item)
                break
        metadata = self._metadata_provider()
        time_text = f'{metadata.frame_time_seconds(frame_index):.3f} s' if metadata is not None else '—'
        self.current_frame_label.setText(f'Frame sorgente {frame_index} · {time_text} · offset ({state.offset_x}, {state.offset_y})')
        self.frame_requested.emit(frame_index)
        self._render_current()

    def _on_output_preset_changed(self) -> None:
        if self._geometry_update_in_progress:
            return
        preset = preset_by_key(str(self.output_size_preset_combo.currentData()))
        if preset.is_custom:
            self._update_geometry_contract()
            return
        self._locked_aspect_ratio = int(preset.width) / int(preset.height)
        self._apply_canvas_size(int(preset.width), int(preset.height))

    def _on_lock_aspect_toggled(self, checked: bool) -> None:
        if checked:
            self._locked_aspect_ratio = self.canvas_width_spin.value() / self.canvas_height_spin.value()
        self._remember_current_alignment_settings()
        self._update_geometry_contract()

    def _on_canvas_width_changed(self, value: int) -> None:
        if self._geometry_update_in_progress:
            return
        width = int(value)
        height = self.canvas_height_spin.value()
        if self.lock_aspect_checkbox.isChecked():
            width, height = locked_size_from_width(width, self._locked_aspect_ratio)
        self._apply_canvas_size(width, height)

    def _on_canvas_height_changed(self, value: int) -> None:
        if self._geometry_update_in_progress:
            return
        width = self.canvas_width_spin.value()
        height = int(value)
        if self.lock_aspect_checkbox.isChecked():
            width, height = locked_size_from_height(height, self._locked_aspect_ratio)
        self._apply_canvas_size(width, height)

    def _apply_canvas_size(self, width: int, height: int) -> None:
        if self._geometry_update_in_progress:
            return
        self._geometry_update_in_progress = True
        try:
            old_width, old_height = self._last_canvas_size
            pivot_x, pivot_y = migrate_canvas_pivot(
                old_width,
                old_height,
                width,
                height,
                self.canvas_pivot_x_spin.value(),
                self.canvas_pivot_y_spin.value(),
                proportional=self.preserve_pivot_checkbox.isChecked(),
            )
            with (
                QSignalBlocker(self.canvas_width_spin),
                QSignalBlocker(self.canvas_height_spin),
                QSignalBlocker(self.canvas_pivot_x_spin),
                QSignalBlocker(self.canvas_pivot_y_spin),
                QSignalBlocker(self.output_size_preset_combo),
            ):
                self.canvas_width_spin.setValue(width)
                self.canvas_height_spin.setValue(height)
                self.canvas_pivot_x_spin.setMaximum(width)
                self.canvas_pivot_y_spin.setMaximum(height)
                self.canvas_pivot_x_spin.setValue(pivot_x)
                self.canvas_pivot_y_spin.setValue(pivot_y)
                preset = preset_for_size(width, height)
                preset_index = self.output_size_preset_combo.findData(preset.key)
                self.output_size_preset_combo.setCurrentIndex(preset_index if preset_index >= 0 else 0)
            self._last_canvas_size = (width, height)
            if not self.lock_aspect_checkbox.isChecked():
                self._locked_aspect_ratio = width / height
        finally:
            self._geometry_update_in_progress = False
        self._on_global_settings_changed()
        if self.auto_fit_resize_checkbox.isChecked() and self._subjects:
            self._fit_all()

    def _apply_geometry_and_fit(self) -> None:
        self._on_global_settings_changed()
        if not self._subjects:
            self.status_message.emit('Formato output applicato. Preparare i frame R2 per calcolare la scala.')
            return
        self._fit_all()
        self._update_geometry_contract()

    def _update_geometry_contract(self) -> None:
        width = self.canvas_width_spin.value()
        height = self.canvas_height_spin.value()
        shape_label = 'quadrato' if width == height else ('orizzontale' if width > height else 'verticale')
        base = (
            f'Output {width} × {height} px · {shape_label} · rapporto {width / height:.4f} · '
            f'pivot ({self.canvas_pivot_x_spin.value():.2f}, {self.canvas_pivot_y_spin.value():.2f})'
        )
        if not self._subjects:
            self.geometry_contract_label.setText(base + ' · nessun frame preparato')
            self.geometry_contract_label.setStyleSheet(
                'QLabel { color: #f4f6f8; padding: 7px; background: #263238; border: 1px solid #607d8b; }'
            )
            return
        self._sync_settings_from_controls()
        try:
            report = analyze_canvas_geometry(self._subjects, self._states, self.settings)
        except Exception as exc:
            self.geometry_contract_label.setText(base + f' · diagnostica non disponibile: {exc}')
            self.geometry_contract_label.setStyleSheet(
                'QLabel { color: #f4f6f8; padding: 7px; background: #4a2d21; border: 1px solid #9e5a3c; }'
            )
            return
        if report.clipped_frames:
            overflow = report.maximum_overflow
            text = (
                base
                + f' · ATTENZIONE: {len(report.clipped_frames)}/{report.total_frames} frame tagliati'
                + f' · overflow max L{overflow[0]} T{overflow[1]} R{overflow[2]} B{overflow[3]} px'
            )
            style = 'QLabel { color: #f4f6f8; padding: 7px; background: #4a2424; border: 1px solid #a94b4b; }'
        elif report.margin_warning_frames:
            text = base + f' · nessun taglio · {len(report.margin_warning_frames)} frame oltre il margine di sicurezza'
            style = 'QLabel { color: #f4f6f8; padding: 7px; background: #493d22; border: 1px solid #9c7d35; }'
        else:
            text = base + f' · {report.total_frames} frame interamente nel margine di sicurezza'
            style = 'QLabel { color: #f4f6f8; padding: 7px; background: #20382a; border: 1px solid #3d7b55; }'
        self.geometry_contract_label.setText(text)
        self.geometry_contract_label.setStyleSheet(style)

    def _sync_settings_from_controls(self) -> None:
        self.settings.canvas_width = self.canvas_width_spin.value()
        self.settings.canvas_height = self.canvas_height_spin.value()
        self.settings.canvas_pivot_x = self.canvas_pivot_x_spin.value()
        self.settings.canvas_pivot_y = self.canvas_pivot_y_spin.value()
        self.settings.margin = self.margin_spin.value()
        self.settings.shared_scale = self.scale_spin.value()
        self.settings.fps = self.fps_spin.value()
        self.settings.loop = self.loop_checkbox.isChecked()
        self.settings.animation_name = self.animation_name_edit.text().strip() or 'walk'
        self.settings.direction = self.direction_combo.currentText().strip() or 'south-east'

    def _on_global_settings_changed(self) -> None:
        max_x = self.canvas_width_spin.value()
        max_y = self.canvas_height_spin.value()
        self.canvas_pivot_x_spin.setMaximum(max_x)
        self.canvas_pivot_y_spin.setMaximum(max_y)
        if self.canvas_pivot_x_spin.value() > max_x:
            self.canvas_pivot_x_spin.setValue(max_x)
        if self.canvas_pivot_y_spin.value() > max_y:
            self.canvas_pivot_y_spin.setValue(max_y)
        self._sync_settings_from_controls()
        self._last_canvas_size = (self.settings.canvas_width, self.settings.canvas_height)
        self.canvas.set_canvas_geometry(self.settings.canvas_width, self.settings.canvas_height, self.settings.canvas_pivot_x, self.settings.canvas_pivot_y)
        self._remember_current_alignment_settings()
        self._render_current()
        self._update_geometry_contract()

    def _on_profile_relevant_setting_changed(self) -> None:
        self._remember_current_alignment_settings()
        self._render_current()
        self._restart_play_timer_if_needed()

    def _on_zoom_changed(self) -> None:
        self.canvas.set_zoom(self.zoom_spin.value())
        self._remember_current_alignment_settings()

    def _on_view_setting_changed(self) -> None:
        self._update_overlays()
        self._remember_current_alignment_settings()
        self._render_current()

    def _on_onion_opacity_changed(self, value: int) -> None:
        self.canvas.set_onion_opacity(value / 100.0)
        self._remember_current_alignment_settings()
        self._render_current()

    def _on_current_state_changed(self) -> None:
        if self._current_frame_index is None:
            return
        state = self._states.get(self._current_frame_index)
        if state is None:
            return
        state.source_pivot_x = self.source_pivot_x_spin.value()
        state.source_pivot_y = self.source_pivot_y_spin.value()
        state.offset_x = self.offset_x_spin.value()
        state.offset_y = self.offset_y_spin.value()
        if self.sender() in (self.source_pivot_x_spin, self.source_pivot_y_spin):
            state.pivot_mode = 'manual'
        self._render_current()

    def _render_current(self) -> None:
        if self._current_frame_index is None or self._current_frame_index not in self._subjects:
            return
        self._sync_settings_from_controls()
        try:
            current_canvas, placement = render_aligned_frame(self._subjects[self._current_frame_index], self._states[self._current_frame_index], self.settings)
        except Exception as exc:
            self.status_message.emit(f'Errore render R2: {exc}')
            return
        self._current_placement = placement
        onion_canvas = None
        if self.onion_checkbox.isChecked() and len(self._selected_indices) > 1:
            current_position = self._selected_indices.index(self._current_frame_index)
            previous_index = self._selected_indices[(current_position - 1) % len(self._selected_indices)]
            onion_canvas, _ = render_aligned_frame(self._subjects[previous_index], self._states[previous_index], self.settings)
        self.canvas.set_canvas_geometry(self.settings.canvas_width, self.settings.canvas_height, self.settings.canvas_pivot_x, self.settings.canvas_pivot_y)
        self.canvas.set_images(current_canvas, onion_canvas)
        self.current_frame_label.setText(f'Frame sorgente {self._current_frame_index} · offset ({self._states[self._current_frame_index].offset_x}, {self._states[self._current_frame_index].offset_y})')
        self._update_geometry_contract()

    def _fit_all(self) -> None:
        if not self._subjects:
            return
        self._sync_settings_from_controls()
        try:
            scale = calculate_shared_fit_scale(self._subjects, self._states, self.settings)
        except ValueError as exc:
            QMessageBox.critical(self, 'Errore adattamento', str(exc))
            return
        self.settings.shared_scale = scale
        self.scale_spin.setValue(scale)
        self._remember_current_alignment_settings()
        self.status_message.emit(f'Scala condivisa calcolata: {scale:.6f}')

    def _estimate_all_anchors(self) -> None:
        mode = str(self.anchor_mode_combo.currentData())
        for frame_index, subject in self._subjects.items():
            pivot_x, pivot_y = estimate_anchor_by_mode(subject.rgba, mode)
            state = self._states[frame_index]
            state.source_pivot_x = pivot_x
            state.source_pivot_y = pivot_y
            state.pivot_mode = 'auto'
            state.anchor_mode = mode
        if self._current_frame_index is not None:
            self._set_current_frame(self._current_frame_index)
        self.status_message.emit('Ancore automatiche ricalcolate.')

    def _estimate_current_anchor(self) -> None:
        if self._current_frame_index is None:
            return
        subject = self._subjects[self._current_frame_index]
        mode = str(self.anchor_mode_combo.currentData())
        pivot_x, pivot_y = estimate_anchor_by_mode(subject.rgba, mode)
        state = self._states[self._current_frame_index]
        state.source_pivot_x = pivot_x
        state.source_pivot_y = pivot_y
        state.pivot_mode = 'auto'
        state.anchor_mode = mode
        self._set_current_frame(self._current_frame_index)

    def _reset_all_offsets(self) -> None:
        for state in self._states.values():
            state.offset_x = 0
            state.offset_y = 0
        if self._current_frame_index is not None:
            self._set_current_frame(self._current_frame_index)

    def _set_bottom_center_pivot(self) -> None:
        width = self.canvas_width_spin.value()
        height = self.canvas_height_spin.value()
        self.canvas_pivot_x_spin.setValue(width / 2.0)
        self.canvas_pivot_y_spin.setValue(max(0, height - 8))
        self._remember_current_alignment_settings()

    def _on_drag_started(self) -> None:
        if self._current_frame_index is None:
            return
        state = self._states[self._current_frame_index]
        self._drag_start_offset = (state.offset_x, state.offset_y)

    def _on_drag_delta(self, dx: int, dy: int) -> None:
        if self._current_frame_index is None:
            return
        start_x, start_y = self._drag_start_offset
        with QSignalBlocker(self.offset_x_spin), QSignalBlocker(self.offset_y_spin):
            self.offset_x_spin.setValue(start_x + dx)
            self.offset_y_spin.setValue(start_y + dy)
        state = self._states[self._current_frame_index]
        state.offset_x = start_x + dx
        state.offset_y = start_y + dy
        self._render_current()

    def _nudge_current(self, dx: int, dy: int) -> None:
        if self._current_frame_index is None:
            return
        state = self._states[self._current_frame_index]
        self.offset_x_spin.setValue(state.offset_x + int(dx))
        self.offset_y_spin.setValue(state.offset_y + int(dy))

    def _on_canvas_pivot_clicked(self, canvas_x: float, canvas_y: float) -> None:
        if self._current_frame_index is None or self._current_placement is None:
            return
        scale = self.settings.shared_scale
        if scale <= 0:
            return
        subject = self._subjects[self._current_frame_index]
        source_x = (canvas_x - self._current_placement.destination_left) / scale
        source_y = (canvas_y - self._current_placement.destination_top) / scale
        source_x = max(0.0, min(float(subject.width), source_x))
        source_y = max(0.0, min(float(subject.height), source_y))
        state = self._states[self._current_frame_index]
        state.source_pivot_x = source_x
        state.source_pivot_y = source_y
        state.pivot_mode = 'manual'
        state.anchor_mode = 'manual'
        self.click_pivot_button.setChecked(False)
        self._set_current_frame(self._current_frame_index)
        self.status_message.emit(f'Ancora manuale impostata: ({source_x:.2f}, {source_y:.2f})')

    def _update_overlays(self) -> None:
        self.canvas.set_overlays(show_grid=self.grid_checkbox.isChecked(), show_pivot=self.pivot_checkbox.isChecked(), show_ground=self.ground_checkbox.isChecked())

    def _select_relative_frame(self, delta: int) -> None:
        if not self._selected_indices:
            return
        if self._current_frame_index not in self._selected_indices:
            self._set_current_frame(self._selected_indices[0])
            return
        position = self._selected_indices.index(self._current_frame_index)
        self._set_current_frame(self._selected_indices[(position + delta) % len(self._selected_indices)])

    def _toggle_loop(self) -> None:
        if self.play_timer.isActive():
            self._stop_loop()
            return
        if not self._subjects:
            self.ensure_prepared()
        if not self._subjects:
            return
        self.onion_checkbox.setChecked(False)
        self.play_timer.start(max(1, int(round(1000 / self.fps_spin.value()))))
        self.play_button.setText('■ Ferma anteprima')

    def _stop_loop(self) -> None:
        self.play_timer.stop()
        self.play_button.setText('▶ Anteprima loop')

    def _restart_play_timer_if_needed(self) -> None:
        if self.play_timer.isActive():
            self.play_timer.start(max(1, int(round(1000 / self.fps_spin.value()))))

    def _advance_loop(self) -> None:
        if not self._selected_indices:
            self._stop_loop()
            return
        if self._current_frame_index not in self._selected_indices:
            self._set_current_frame(self._selected_indices[0])
            return
        position = self._selected_indices.index(self._current_frame_index)
        if position == len(self._selected_indices) - 1:
            if not self.loop_checkbox.isChecked():
                self._stop_loop()
                return
            position = -1
        self._set_current_frame(self._selected_indices[position + 1])

    def snapshot_session(self) -> dict:
        return {
            'profile': self._capture_alignment_profile_data(),
            'selected_indices': list(self._selected_indices),
            'frame_states': {str(index): state.to_dict() for index, state in self._states.items()},
        }

    def restore_session(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        profile = data.get('profile')
        if isinstance(profile, dict):
            self._apply_alignment_profile_data(profile, persist_last=False)
        pending: dict[int, FrameAlignmentState] = {}
        frame_states = data.get('frame_states')
        if isinstance(frame_states, dict):
            for key, value in frame_states.items():
                if not isinstance(value, dict):
                    continue
                try:
                    frame_index = int(value.get('frame_index', key))
                    source_pivot = value.get('source_pivot', [0.0, 0.0])
                    offset = value.get('offset', [0, 0])
                    pending[frame_index] = FrameAlignmentState(
                        frame_index=frame_index,
                        source_pivot_x=float(source_pivot[0]),
                        source_pivot_y=float(source_pivot[1]),
                        offset_x=int(offset[0]),
                        offset_y=int(offset[1]),
                        pivot_mode=str(value.get('pivot_mode', 'auto')),
                        anchor_mode=str(value.get('anchor_mode', 'ground')),
                    )
                except Exception:
                    continue
        self._pending_restored_states = pending
        self.mark_dirty('Sessione R2 ripristinata: aggiorna dai frame R1 per ricostruire le sagome con gli offset salvati.')

    def build_export_payload(self) -> dict:
        self.ensure_prepared()
        metadata = self._metadata_provider()
        if metadata is None or not self._subjects or not self._selected_indices:
            raise RuntimeError('R2 non pronta: preparare almeno un set di frame allineati.')
        self._sync_settings_from_controls()
        rendered_frames = []
        for frame_index in self._selected_indices:
            canvas, _ = render_aligned_frame(self._subjects[frame_index], self._states[frame_index], self.settings)
            rendered_frames.append(canvas)
        return {
            'rgba_frames': rendered_frames,
            'default_base_name': f"{self.animation_name_edit.text().strip() or 'animation'}-{self.direction_combo.currentText().strip() or 'direction'}",
            'suggested_output_dir': str(metadata.path.parent),
            'metadata': {
                'animation_name': self.animation_name_edit.text().strip() or 'animation',
                'direction': self.direction_combo.currentText().strip() or 'direction',
                'fps': self.fps_spin.value(),
                'loop': self.loop_checkbox.isChecked(),
                'canvas': self.settings.to_dict(),
                'selected_frame_indices': list(self._selected_indices),
            },
        }

    def _export_animation(self) -> None:
        if self._dirty:
            QMessageBox.information(self, 'R2 da aggiornare', 'Aggiornare R2 dai frame R1 prima di esportare.')
            return
        metadata = self._metadata_provider()
        if metadata is None or not self._subjects:
            return
        output_dir = QFileDialog.getExistingDirectory(self, 'Cartella di esportazione animazione', str(metadata.path.parent))
        if not output_dir:
            return
        self._sync_settings_from_controls()
        geometry_report = analyze_canvas_geometry(self._subjects, self._states, self.settings)
        if geometry_report.clipped_frames:
            answer = QMessageBox.question(
                self,
                'Frame tagliati dal formato output',
                f'{len(geometry_report.clipped_frames)} frame su {geometry_report.total_frames} superano la tela '
                f'{self.settings.canvas_width}×{self.settings.canvas_height}. Continuare comunque con l’esportazione?',
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        output_format = 'png' if self.export_format_combo.currentIndex() == 0 else 'webp'
        layout = ('horizontal', 'grid', 'vertical')[self.sheet_layout_combo.currentIndex()]
        mirror_mode = str(self.mirror_export_combo.currentData())
        variant_count = 2 if mirror_mode == 'opposite-lateral' else 1
        progress = QProgressDialog('Esportazione animazione R2…', 'Annulla', 0, variant_count * (len(self._selected_indices) + 1), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        cancelled = False

        def on_progress(position: int, total: int, frame_index: int) -> None:
            nonlocal cancelled
            if frame_index >= 0:
                progress.setLabelText(f'Esportazione frame {frame_index} ({position}/{total})')
            else:
                progress.setLabelText(f'Creazione sprite sheet… ({position}/{total})')
            progress.setMaximum(total)
            progress.setValue(position)
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            if progress.wasCanceled():
                cancelled = True
                raise AlignmentExportError('Esportazione annullata dall\'utente.')

        try:
            manifest = export_aligned_animation(
                frame_indices=self._selected_indices,
                subjects=self._subjects,
                states=self._states,
                video_metadata=metadata,
                chroma_settings=self._chroma_provider(),
                alignment_settings=self.settings,
                output_directory=output_dir,
                animation_name=self.animation_name_edit.text(),
                direction=self.direction_combo.currentText(),
                output_format=output_format,
                sheet_layout=layout,
                sheet_columns=self.sheet_columns_spin.value(),
                sheet_padding=self.sheet_padding_spin.value(),
                mirror_mode=mirror_mode,
                progress_callback=on_progress,
            )
        except Exception as exc:
            progress.close()
            if not cancelled:
                QMessageBox.critical(self, 'Errore esportazione R2', str(exc))
            return
        progress.close()
        generated = manifest.get('generated_exports', [])
        if generated:
            exported_labels = ', '.join(item.get('direction', '?') for item in generated)
            message = f'Esportati {manifest["animation"]["frame_count"]} frame allineati.\nDirezioni generate: {exported_labels}.\nOutput in:\n{output_dir}'
        else:
            message = f'Esportati {manifest["animation"]["frame_count"]} frame allineati, sprite sheet e manifest in:\n{output_dir}'
        QMessageBox.information(self, 'Animazione esportata', message)
        self.status_message.emit('Esportazione R2 completata.')

