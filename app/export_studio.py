from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QLineEdit,
    QInputDialog,
)

from app.export_service import ExportError, export_rgba_bundle
from app.profile_store import ProfilesStore


class ExportStudio(QWidget):
    export_completed = Signal(dict)
    status_message = Signal(str)

    def __init__(
        self,
        *,
        raw_frames_provider: Callable[[], dict],
        aligned_frames_provider: Callable[[], dict],
    ) -> None:
        super().__init__()
        self._raw_frames_provider = raw_frames_provider
        self._aligned_frames_provider = aligned_frames_provider
        self.profile_store = ProfilesStore()
        self.background_rgb = (0, 0, 0)
        self._build_ui()
        self._refresh_export_profiles_combo()
        self._load_last_used_export_profile()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)

        intro = QLabel(
            'R5e4 Export Studio — final production output. Export individual frames and sprite sheets from the R1 selection or aligned R2 frames, with configurable layout, final scale, and background.'
        )
        intro.setWordWrap(True)
        intro.setStyleSheet('QLabel { color: #f4f6f8; padding: 10px; background: #24313a; border: 1px solid #536b78; }')
        layout.addWidget(intro)

        profiles_group = QGroupBox('Export Profiles')
        profiles_form = QFormLayout(profiles_group)
        self.export_profile_combo = QComboBox()
        profile_actions = QWidget()
        profile_row = QHBoxLayout(profile_actions)
        profile_row.setContentsMargins(0, 0, 0, 0)
        load_button = QPushButton('Load')
        save_button = QPushButton('Save Current')
        delete_button = QPushButton('Delete')
        load_button.clicked.connect(self._load_selected_export_profile)
        save_button.clicked.connect(self._save_current_export_profile_as)
        delete_button.clicked.connect(self._delete_selected_export_profile)
        profile_row.addWidget(load_button)
        profile_row.addWidget(delete_button)
        profile_row.addWidget(save_button)
        profiles_form.addRow('Profile', self.export_profile_combo)
        profiles_form.addRow('', profile_actions)
        layout.addWidget(profiles_group)

        source_group = QGroupBox('Source and Destination')
        source_form = QFormLayout(source_group)
        self.source_combo = QComboBox()
        self.source_combo.addItem('R1 selected frames (raw/chroma)', 'raw')
        self.source_combo.addItem('R2 aligned frames', 'aligned')
        self.base_name_edit = QLineEdit('walk-se')
        self.output_format_combo = QComboBox(); self.output_format_combo.addItems(['PNG', 'WebP lossless'])
        self.output_path_label = QLabel('The folder is selected when you export')
        self.output_path_label.setWordWrap(True)
        source_form.addRow('Source', self.source_combo)
        source_form.addRow('Output base name', self.base_name_edit)
        source_form.addRow('Format', self.output_format_combo)
        source_form.addRow('Destination', self.output_path_label)
        layout.addWidget(source_group)

        product_group = QGroupBox('Outputs to Generate')
        product_form = QFormLayout(product_group)
        self.include_frames_checkbox = QCheckBox('Export Individual Frames')
        self.include_frames_checkbox.setChecked(True)
        self.include_sheet_checkbox = QCheckBox('Export Sprite Sheet')
        self.include_sheet_checkbox.setChecked(True)
        self.sheet_layout_combo = QComboBox(); self.sheet_layout_combo.addItems(['Inline', 'Gallery / Grid', 'Vertical'])
        self.sheet_columns_spin = QSpinBox(); self.sheet_columns_spin.setRange(1, 64); self.sheet_columns_spin.setValue(8)
        self.sheet_padding_spin = QSpinBox(); self.sheet_padding_spin.setRange(0, 128); self.sheet_padding_spin.setValue(0)
        product_form.addRow('', self.include_frames_checkbox)
        product_form.addRow('', self.include_sheet_checkbox)
        product_form.addRow('Layout sheet', self.sheet_layout_combo)
        product_form.addRow('Grid Columns', self.sheet_columns_spin)
        product_form.addRow('Spaziatura', self.sheet_padding_spin)
        layout.addWidget(product_group)

        transform_group = QGroupBox('Final Resolution and Background')
        transform_form = QFormLayout(transform_group)
        self.scale_factor_spin = QSpinBox(); self.scale_factor_spin.setRange(1, 8); self.scale_factor_spin.setValue(1)
        self.background_mode_combo = QComboBox()
        self.background_mode_combo.addItem('Transparent', 'transparent')
        self.background_mode_combo.addItem('Pieno', 'solid')
        self.background_button = QPushButton('Choose Color')
        self.background_swatch = QLabel('')
        self.background_swatch.setFixedWidth(48)
        self.background_button.clicked.connect(self._pick_background_color)
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.background_button)
        color_layout.addWidget(self.background_swatch)
        color_layout.addStretch(1)
        transform_form.addRow('Final scale', self.scale_factor_spin)
        transform_form.addRow('Background', self.background_mode_combo)
        transform_form.addRow('Background Color', color_row)
        layout.addWidget(transform_group)
        self._update_background_swatch()

        action_row = QHBoxLayout()
        export_button = QPushButton('Export Final Package')
        export_button.clicked.connect(self._export_package)
        action_row.addWidget(export_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)
        layout.addStretch(1)

        for control in (
            self.source_combo, self.output_format_combo, self.sheet_layout_combo, self.sheet_columns_spin,
            self.sheet_padding_spin, self.scale_factor_spin, self.background_mode_combo,
        ):
            signal = getattr(control, 'currentIndexChanged', None) or getattr(control, 'valueChanged', None)
            signal.connect(self._remember_current_export_profile)
        self.base_name_edit.textChanged.connect(self._remember_current_export_profile)
        self.include_frames_checkbox.toggled.connect(self._remember_current_export_profile)
        self.include_sheet_checkbox.toggled.connect(self._remember_current_export_profile)

    def _update_background_swatch(self) -> None:
        r, g, b = self.background_rgb
        self.background_swatch.setStyleSheet(f'QLabel {{ color: #f4f6f8; background: rgb({r}, {g}, {b}); border: 1px solid #777; }}')

    def _pick_background_color(self) -> None:
        color = QColorDialog.getColor(QColor(*self.background_rgb), self, 'Export Background Color')
        if not color.isValid():
            return
        self.background_rgb = (color.red(), color.green(), color.blue())
        self._update_background_swatch()
        self._remember_current_export_profile()

    def _capture_export_profile_data(self) -> dict:
        return {
            'source_mode': str(self.source_combo.currentData()),
            'base_name': self.base_name_edit.text().strip(),
            'output_format_index': self.output_format_combo.currentIndex(),
            'include_frames': self.include_frames_checkbox.isChecked(),
            'include_sheet': self.include_sheet_checkbox.isChecked(),
            'sheet_layout_index': self.sheet_layout_combo.currentIndex(),
            'sheet_columns': self.sheet_columns_spin.value(),
            'sheet_padding': self.sheet_padding_spin.value(),
            'scale_factor': self.scale_factor_spin.value(),
            'background_mode': str(self.background_mode_combo.currentData()),
            'background_rgb': list(self.background_rgb),
        }

    def _apply_export_profile_data(self, data: dict, *, persist_last: bool = True) -> None:
        src_idx = self.source_combo.findData(str(data.get('source_mode', self.source_combo.currentData())))
        if src_idx >= 0:
            self.source_combo.setCurrentIndex(src_idx)
        self.base_name_edit.setText(str(data.get('base_name', self.base_name_edit.text())))
        self.output_format_combo.setCurrentIndex(int(data.get('output_format_index', self.output_format_combo.currentIndex())))
        self.include_frames_checkbox.setChecked(bool(data.get('include_frames', self.include_frames_checkbox.isChecked())))
        self.include_sheet_checkbox.setChecked(bool(data.get('include_sheet', self.include_sheet_checkbox.isChecked())))
        self.sheet_layout_combo.setCurrentIndex(int(data.get('sheet_layout_index', self.sheet_layout_combo.currentIndex())))
        self.sheet_columns_spin.setValue(int(data.get('sheet_columns', self.sheet_columns_spin.value())))
        self.sheet_padding_spin.setValue(int(data.get('sheet_padding', self.sheet_padding_spin.value())))
        self.scale_factor_spin.setValue(int(data.get('scale_factor', self.scale_factor_spin.value())))
        mode = str(data.get('background_mode', self.background_mode_combo.currentData()))
        mode_idx = self.background_mode_combo.findData(mode)
        if mode_idx >= 0:
            self.background_mode_combo.setCurrentIndex(mode_idx)
        rgb = data.get('background_rgb')
        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
            self.background_rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            self._update_background_swatch()
        if persist_last:
            self.profile_store.set_last_used('export', self._capture_export_profile_data())

    def _remember_current_export_profile(self, *_args) -> None:
        try:
            self.profile_store.set_last_used('export', self._capture_export_profile_data())
        except Exception:
            return

    def _refresh_export_profiles_combo(self, selected: str | None = None) -> None:
        names = self.profile_store.list_profiles('export')
        self.export_profile_combo.clear()
        self.export_profile_combo.addItems(names)
        if selected and selected in names:
            self.export_profile_combo.setCurrentText(selected)

    def _load_last_used_export_profile(self) -> None:
        data = self.profile_store.get_last_used('export')
        if data:
            self._apply_export_profile_data(data, persist_last=False)

    def _save_current_export_profile_as(self) -> None:
        name, ok = QInputDialog.getText(self, 'Save Export Profile', 'Profile name:')
        if not ok or not name.strip():
            return
        normalized = name.strip()
        self.profile_store.set_profile('export', normalized, self._capture_export_profile_data())
        self._refresh_export_profiles_combo(normalized)
        self.status_message.emit(f'Export profile saved: {normalized}')

    def _load_selected_export_profile(self) -> None:
        name = self.export_profile_combo.currentText().strip()
        if not name:
            return
        data = self.profile_store.get_profile('export', name)
        if data is None:
            QMessageBox.information(self, 'Profile Not Found', 'The selected export profile is not available.')
            self._refresh_export_profiles_combo()
            return
        self._apply_export_profile_data(data)
        self.status_message.emit(f'Export profile loaded: {name}')

    def _delete_selected_export_profile(self) -> None:
        name = self.export_profile_combo.currentText().strip()
        if not name:
            return
        answer = QMessageBox.question(self, 'Delete Export Profile', f'Delete profile "{name}"?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.profile_store.delete_profile('export', name)
        self._refresh_export_profiles_combo()
        self.status_message.emit(f'Export profile deleted: {name}')

    def snapshot_state(self) -> dict:
        return self._capture_export_profile_data()

    def apply_state(self, data: dict) -> None:
        if isinstance(data, dict):
            self._apply_export_profile_data(data, persist_last=False)

    def _export_package(self) -> None:
        source_mode = str(self.source_combo.currentData())
        try:
            source_payload = self._raw_frames_provider() if source_mode == 'raw' else self._aligned_frames_provider()
        except Exception as exc:
            QMessageBox.critical(self, 'Export Source Error', str(exc))
            return
        rgba_frames = source_payload.get('rgba_frames')
        if not isinstance(rgba_frames, list) or not rgba_frames:
            QMessageBox.information(self, 'No Frames', 'The selected source has no exportable frames.')
            return
        suggested_dir = source_payload.get('suggested_output_dir') or source_payload.get('source_dir') or str(Path.home())
        output_dir = QFileDialog.getExistingDirectory(self, 'Final Export Folder', str(suggested_dir))
        if not output_dir:
            return
        layout_map = {0: 'horizontal', 1: 'grid', 2: 'vertical'}
        ext = 'png' if self.output_format_combo.currentIndex() == 0 else 'webp'
        base_name = self.base_name_edit.text().strip() or str(source_payload.get('default_base_name', 'animation'))
        try:
            manifest = export_rgba_bundle(
                rgba_frames=rgba_frames,
                output_directory=output_dir,
                base_name=base_name,
                output_format=ext,
                include_frames=self.include_frames_checkbox.isChecked(),
                include_sheet=self.include_sheet_checkbox.isChecked(),
                sheet_layout=layout_map.get(self.sheet_layout_combo.currentIndex(), 'horizontal'),
                sheet_columns=self.sheet_columns_spin.value(),
                sheet_padding=self.sheet_padding_spin.value(),
                scale_factor=self.scale_factor_spin.value(),
                background_mode=str(self.background_mode_combo.currentData()),
                background_rgb=self.background_rgb,
                source_kind=source_mode,
                metadata=source_payload.get('metadata', {}),
            )
        except ExportError as exc:
            QMessageBox.critical(self, 'Final Export Error', str(exc))
            return
        message = [f"Exported {manifest['frame_count']} frame."]
        if manifest.get('sheet'):
            sheet = manifest['sheet']
            message.append(f"Sprite sheet: {sheet['layout']} · {sheet['columns']}×{sheet['rows']} · {sheet['width']}×{sheet['height']} px")
        message.append(f'Output in:\n{output_dir}')
        QMessageBox.information(self, 'Final export completed', '\n'.join(message))
        self.export_completed.emit({'output_directory': str(output_dir), 'manifest': manifest})
        self.status_message.emit('R5e4 Export Studio: export completed.')
