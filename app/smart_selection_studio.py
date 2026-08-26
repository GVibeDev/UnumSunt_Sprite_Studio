from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from collections.abc import Callable
from typing import Optional

import numpy as np
from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.frame_analysis import (
    PROFILE_DEFAULTS,
    SmartSelectionResult,
    analyze_and_select,
    extract_frame_feature,
    sensitivity_to_duplicate_threshold,
)
from app.models import ChromaKeySettings, VideoMetadata
from app.selected_frames_player import SelectedFramesPlayer


class SmartSelectionStudio(QWidget):
    frame_requested = Signal(int)
    selection_applied = Signal(list)
    status_message = Signal(str)

    def __init__(
        self,
        *,
        frame_loader: Callable[[int], np.ndarray],
        metadata_provider: Callable[[], Optional[VideoMetadata]],
        chroma_provider: Callable[[], ChromaKeySettings],
        current_frame_provider: Callable[[], int],
        rgba_override_provider: Callable[[int], np.ndarray | None] | None = None,
    ) -> None:
        super().__init__()
        self._frame_loader = frame_loader
        self._metadata_provider = metadata_provider
        self._chroma_provider = chroma_provider
        self._current_frame_provider = current_frame_provider
        self._rgba_override_provider = rgba_override_provider

        self._r1_indices: list[int] = []
        self._result: SmartSelectionResult | None = None
        self._dirty = True
        self._updating_table = False

        self._build_ui()
        self._set_analysis_controls_enabled(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        self.state_label = QLabel(
            'Open a video, define the range, and start the R3 analysis.'
        )
        self.state_label.setWordWrap(True)
        self.state_label.setStyleSheet(
            "QLabel { color: #f4f6f8; padding: 6px; background: #302a20; "
            "border: 1px solid #74643f; }"
        )
        root.addWidget(self.state_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        player_group = QGroupBox('Selected Frame Player')
        player_layout = QVBoxLayout(player_group)
        self.player = SelectedFramesPlayer(
            frame_loader=self._frame_loader,
            chroma_provider=self._chroma_provider,
            rgba_override_provider=self._rgba_override_provider,
        )
        self.player.frame_requested.connect(self.frame_requested)
        self.player.status_message.connect(self.status_message)
        player_layout.addWidget(self.player)
        left_layout.addWidget(player_group, 1)

        summary_group = QGroupBox("Sintesi analisi")
        summary_grid = QGridLayout(summary_group)
        self.summary_labels: dict[str, QLabel] = {}
        labels = (
            ('Analyzed', "analyzed"),
            ("Suggeriti", "suggested"),
            ('Near duplicates', "duplicates"),
            ("Anomalie", "anomalies"),
            ('Loop Quality', "loop"),
            ('Total motion', "motion"),
        )
        for position, (title, key) in enumerate(labels):
            row = position // 3
            column = position % 3
            box = QWidget()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(4, 4, 4, 4)
            title_label = QLabel(title)
            title_label.setStyleSheet("color: #949aa6;")
            value_label = QLabel("—")
            value_label.setStyleSheet("font-size: 18px; font-weight: 600;")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_layout.addWidget(title_label)
            box_layout.addWidget(value_label)
            summary_grid.addWidget(box, row, column)
            self.summary_labels[key] = value_label
        left_layout.addWidget(summary_group)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        settings_group = QGroupBox('Range and Profile')
        settings_form = QFormLayout(settings_group)

        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 0)
        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, 0)

        start_widget = QWidget()
        start_layout = QHBoxLayout(start_widget)
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_layout.addWidget(self.start_spin, 1)
        start_current_button = QPushButton('Current frame')
        start_current_button.clicked.connect(
            lambda: self.start_spin.setValue(self._current_frame_provider())
        )
        start_layout.addWidget(start_current_button)

        end_widget = QWidget()
        end_layout = QHBoxLayout(end_widget)
        end_layout.setContentsMargins(0, 0, 0, 0)
        end_layout.addWidget(self.end_spin, 1)
        end_current_button = QPushButton('Current frame')
        end_current_button.clicked.connect(
            lambda: self.end_spin.setValue(self._current_frame_provider())
        )
        end_layout.addWidget(end_current_button)

        self.sample_step_spin = QSpinBox()
        self.sample_step_spin.setRange(1, 120)
        self.sample_step_spin.setValue(1)

        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Idle", "idle")
        self.profile_combo.addItem("Walk", "walk")
        self.profile_combo.addItem("Run", "run")
        self.profile_combo.addItem("Interact", "interact")
        self.profile_combo.currentIndexChanged.connect(
            lambda *_: self._apply_profile_default()
        )

        self.desired_spin = QSpinBox()
        self.desired_spin.setRange(1, 64)
        self.desired_spin.setValue(PROFILE_DEFAULTS["idle"])

        self.duplicate_sensitivity_spin = QSpinBox()
        self.duplicate_sensitivity_spin.setRange(0, 100)
        self.duplicate_sensitivity_spin.setValue(15)
        self.duplicate_sensitivity_spin.setSuffix(" %")

        self.avoid_anomalies_checkbox = QCheckBox(
            'Avoid strong anomalies in the proposal'
        )
        self.avoid_anomalies_checkbox.setChecked(True)

        settings_form.addRow("Inizio", start_widget)
        settings_form.addRow("Fine", end_widget)
        settings_form.addRow("Analizza ogni", self.sample_step_spin)
        settings_form.addRow('Profile', self.profile_combo)
        settings_form.addRow('Desired frames', self.desired_spin)
        settings_form.addRow(
            'Duplicate Sensitivity',
            self.duplicate_sensitivity_spin,
        )
        settings_form.addRow("", self.avoid_anomalies_checkbox)
        right_layout.addWidget(settings_group)

        action_row = QHBoxLayout()
        self.analyze_button = QPushButton('Analyze and Suggest')
        self.analyze_button.clicked.connect(self.analyze)
        self.restore_button = QPushButton('Reset Suggestion')
        self.restore_button.clicked.connect(self._restore_suggestions)
        self.r1_button = QPushButton('Check R1 Selection')
        self.r1_button.clicked.connect(self._check_r1_selection)
        action_row.addWidget(self.analyze_button)
        action_row.addWidget(self.restore_button)
        action_row.addWidget(self.r1_button)
        right_layout.addLayout(action_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                'Use',
                "Frame",
                "Tempo",
                "Motion",
                "Anomalia",
                'Quality',
                "Note",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.itemSelectionChanged.connect(
            self._on_table_selection_changed
        )
        right_layout.addWidget(self.table, 1)

        bottom_row = QHBoxLayout()
        export_report_button = QPushButton('Export JSON Report')
        export_report_button.clicked.connect(self._export_report)
        self.apply_button = QPushButton('Apply Checked Frames to R1 Selection')
        self.apply_button.clicked.connect(self._apply_checked_to_r1)
        bottom_row.addWidget(export_report_button)
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.apply_button)
        right_layout.addLayout(bottom_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([650, 760])
        root.addWidget(splitter, 1)

        for control in (
            self.start_spin,
            self.end_spin,
            self.sample_step_spin,
            self.profile_combo,
            self.desired_spin,
            self.duplicate_sensitivity_spin,
            self.avoid_anomalies_checkbox,
        ):
            if hasattr(control, "valueChanged"):
                control.valueChanged.connect(
                    lambda *_: self.mark_dirty()
                )
            elif hasattr(control, "currentIndexChanged"):
                control.currentIndexChanged.connect(
                    lambda *_: self.mark_dirty()
                )
            elif hasattr(control, "toggled"):
                control.toggled.connect(
                    lambda *_: self.mark_dirty()
                )

    def set_video_metadata(self, metadata: VideoMetadata | None) -> None:
        self.player.stop()
        self._result = None
        self.table.setRowCount(0)
        self._clear_summary()

        if metadata is None:
            self.start_spin.setRange(0, 0)
            self.end_spin.setRange(0, 0)
            self._set_analysis_controls_enabled(False)
            self.state_label.setText('No video loaded.')
            return

        maximum = max(0, metadata.frame_count - 1)
        with QSignalBlocker(self.start_spin), QSignalBlocker(self.end_spin):
            self.start_spin.setRange(0, maximum)
            self.end_spin.setRange(0, maximum)
            self.start_spin.setValue(0)
            self.end_spin.setValue(maximum)
        self._set_analysis_controls_enabled(True)
        self.mark_dirty(
            f'Video ready: {metadata.frame_count} frames. Define the range and start the analysis.'
        )

    def set_r1_selection(self, indices: list[int]) -> None:
        self._r1_indices = sorted(set(int(index) for index in indices))
        self.player.set_r1_indices(self._r1_indices)

    def mark_dirty(self, message: str | None = None) -> None:
        self._dirty = True
        self.state_label.setText(
            message
            or 'Parameters or chroma key changed: repeat the R3 analysis.'
        )
        self.state_label.setStyleSheet(
            "QLabel { color: #f4f6f8; padding: 6px; background: #302a20; "
            "border: 1px solid #74643f; }"
        )
        self.player.invalidate_cache()

    def snapshot_state(self) -> dict:
        return {
            'start_frame': int(self.start_spin.value()),
            'end_frame': int(self.end_spin.value()),
            'sample_step': int(self.sample_step_spin.value()),
            'profile': str(self.profile_combo.currentData()),
            'desired_frames': int(self.desired_spin.value()),
            'duplicate_sensitivity': int(self.duplicate_sensitivity_spin.value()),
            'avoid_anomalies': bool(self.avoid_anomalies_checkbox.isChecked()),
            'r1_selection': list(self._r1_indices),
        }

    def apply_state(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        profile = str(data.get('profile', self.profile_combo.currentData()))
        idx = self.profile_combo.findData(profile)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
        self.start_spin.setValue(max(self.start_spin.minimum(), min(self.start_spin.maximum(), int(data.get('start_frame', self.start_spin.value())))))
        self.end_spin.setValue(max(self.end_spin.minimum(), min(self.end_spin.maximum(), int(data.get('end_frame', self.end_spin.value())))))
        self.sample_step_spin.setValue(int(data.get('sample_step', self.sample_step_spin.value())))
        self.desired_spin.setValue(int(data.get('desired_frames', self.desired_spin.value())))
        self.duplicate_sensitivity_spin.setValue(int(data.get('duplicate_sensitivity', self.duplicate_sensitivity_spin.value())))
        self.avoid_anomalies_checkbox.setChecked(bool(data.get('avoid_anomalies', self.avoid_anomalies_checkbox.isChecked())))
        selection = data.get('r1_selection')
        if isinstance(selection, list):
            self.set_r1_selection([int(v) for v in selection if isinstance(v, int) or str(v).isdigit()])
        self.mark_dirty('R3 settings restored from the active group.')

    def clear_project(self) -> None:
        self.player.clear()
        self._r1_indices.clear()
        self._result = None
        self.table.setRowCount(0)
        self._clear_summary()
        self.set_video_metadata(None)

    def analyze(self) -> None:
        metadata = self._metadata_provider()
        if metadata is None:
            QMessageBox.information(
                self,
                'No Video',
                'Open a video in the R1 Extraction tab first.',
            )
            return

        start = self.start_spin.value()
        end = self.end_spin.value()
        if end < start:
            QMessageBox.warning(
                self,
                'Invalid Range',
                'The end frame must be equal to or later than the start frame.',
            )
            return

        step = self.sample_step_spin.value()
        indices = list(range(start, end + 1, step))
        if not indices or indices[-1] != end:
            indices.append(end)
        indices = sorted(set(indices))

        desired = self.desired_spin.value()
        if len(indices) < desired:
            QMessageBox.warning(
                self,
                'Insufficient sample',
                f"L'intervallo produce {len(indices)} frames analyzed, but required: {desired}. Reduce the requested count or the sampling step.",
            )
            return

        progress = QProgressDialog(
            'Analyzing frames intelligently…',
            'Cancel',
            0,
            len(indices),
            self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        features = []
        chroma = self._chroma_provider()
        try:
            from PySide6.QtWidgets import QApplication

            for position, frame_index in enumerate(indices, start=1):
                if progress.wasCanceled():
                    progress.close()
                    return
                progress.setLabelText(
                    f"Analisi frame {frame_index} ({position}/{len(indices)})"
                )
                source_rgb = self._frame_loader(frame_index)
                feature = extract_frame_feature(
                    frame_index=frame_index,
                    time_seconds=metadata.frame_time_seconds(frame_index),
                    image_rgb=source_rgb,
                    chroma_settings=chroma,
                )
                features.append(feature)
                progress.setValue(position)
                QApplication.processEvents()
        except Exception as exc:
            progress.close()
            QMessageBox.critical(
                self,
                "Analisi interrotta",
                str(exc),
            )
            return
        progress.close()

        profile = str(self.profile_combo.currentData())
        threshold = sensitivity_to_duplicate_threshold(
            self.duplicate_sensitivity_spin.value()
        )
        try:
            result = analyze_and_select(
                features=features,
                profile=profile,
                desired_count=desired,
                duplicate_threshold=threshold,
                avoid_strong_anomalies=self.avoid_anomalies_checkbox.isChecked(),
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                'R3 Analysis Error',
                str(exc),
            )
            return

        self._result = result
        self._dirty = False
        self._populate_table(result)
        self._update_summary(result)
        self.player.set_r3_indices(result.suggestions)
        self.player.source_combo.setCurrentIndex(0)

        self.state_label.setText(
            f'Analysis completed: {len(result.features)} frames examined, {len(result.suggestions)} suggested for profile {profile}.'
        )
        self.state_label.setStyleSheet(
            "QLabel { color: #f4f6f8; padding: 6px; background: #20382a; "
            "border: 1px solid #3d7b55; }"
        )
        self.status_message.emit('R3 analysis completed.')

    def _populate_table(self, result: SmartSelectionResult) -> None:
        self._updating_table = True
        self.table.setRowCount(len(result.features))
        suggested = set(result.suggestions)

        for row, feature in enumerate(result.features):
            use_item = QTableWidgetItem()
            use_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            use_item.setCheckState(
                Qt.CheckState.Checked
                if feature.frame_index in suggested
                else Qt.CheckState.Unchecked
            )
            use_item.setData(
                Qt.ItemDataRole.UserRole,
                feature.frame_index,
            )
            self.table.setItem(row, 0, use_item)

            values = (
                str(feature.frame_index),
                f"{feature.time_seconds:.3f} s",
                f"{feature.motion_from_previous:.4f}",
                f"{feature.anomaly_score:.2f}",
                f"{feature.quality_score * 100:.0f}%",
                ", ".join(feature.flags) if feature.flags else "—",
            )
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    feature.frame_index,
                )
                self.table.setItem(row, column, item)

        self._updating_table = False
        self._sync_player_from_checked()

    def _checked_indices(self) -> list[int]:
        checked = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                checked.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return sorted(set(checked))

    def _sync_player_from_checked(self) -> None:
        self.player.set_r3_indices(self._checked_indices())

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table or item.column() != 0:
            return
        self._sync_player_from_checked()

    def _on_table_selection_changed(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if item is None:
            return
        frame_index = int(item.data(Qt.ItemDataRole.UserRole))
        self.player.preview_frame(frame_index)

    def _restore_suggestions(self) -> None:
        if self._result is None:
            return
        suggested = set(self._result.suggestions)
        self._updating_table = True
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            frame_index = int(item.data(Qt.ItemDataRole.UserRole))
            item.setCheckState(
                Qt.CheckState.Checked
                if frame_index in suggested
                else Qt.CheckState.Unchecked
            )
        self._updating_table = False
        self._sync_player_from_checked()

    def _check_r1_selection(self) -> None:
        if self._result is None:
            return
        r1 = set(self._r1_indices)
        self._updating_table = True
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            frame_index = int(item.data(Qt.ItemDataRole.UserRole))
            item.setCheckState(
                Qt.CheckState.Checked
                if frame_index in r1
                else Qt.CheckState.Unchecked
            )
        self._updating_table = False
        self._sync_player_from_checked()

    def _apply_checked_to_r1(self) -> None:
        if self._dirty:
            QMessageBox.information(
                self,
                'Analysis Out of Date',
                'Repeat the R3 analysis before applying the selection.',
            )
            return
        checked = self._checked_indices()
        if not checked:
            QMessageBox.information(
                self,
                'No Frames',
                'Check at least one frame before applying the selection.',
            )
            return
        self.selection_applied.emit(checked)
        self.status_message.emit(
            f'Applied {len(checked)} frames to the R1 selection.'
        )

    def _export_report(self) -> None:
        if self._dirty:
            QMessageBox.information(
                self,
                'Analysis Out of Date',
                'Repeat the R3 analysis before exporting the report.',
            )
            return
        if self._result is None:
            QMessageBox.information(
                self,
                'No Analysis',
                "Run the R3 analysis first.",
            )
            return
        metadata = self._metadata_provider()
        if metadata is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            'Export R3 Analysis Report',
            str(metadata.path.with_name(metadata.path.stem + "-frame-analysis-r3.json")),
            "JSON (*.json)",
        )
        if not path:
            return

        report = self._result.to_dict()
        report["application_version"] = "R3a"
        report["exported_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["source_video"] = {
            "path": str(metadata.path),
            "filename": metadata.path.name,
            "width": metadata.width,
            "height": metadata.height,
            "fps": metadata.fps,
            "frame_count": metadata.frame_count,
        }
        report["checked_frames"] = self._checked_indices()
        report["analysis_interval"] = {
            "start": self.start_spin.value(),
            "end": self.end_spin.value(),
            "sample_step": self.sample_step_spin.value(),
        }
        report["chroma_key"] = self._chroma_provider().to_dict()

        try:
            Path(path).write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                'Save Error',
                str(exc),
            )
            return
        self.status_message.emit('R3 report exported.')

    def _apply_profile_default(self) -> None:
        profile = str(self.profile_combo.currentData())
        default = PROFILE_DEFAULTS.get(profile, 8)
        with QSignalBlocker(self.desired_spin):
            self.desired_spin.setValue(default)
        self.mark_dirty()

    def _set_analysis_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.start_spin,
            self.end_spin,
            self.sample_step_spin,
            self.profile_combo,
            self.desired_spin,
            self.duplicate_sensitivity_spin,
            self.avoid_anomalies_checkbox,
            self.analyze_button,
            self.restore_button,
            self.r1_button,
            self.apply_button,
        ):
            widget.setEnabled(enabled)

    def _update_summary(self, result: SmartSelectionResult) -> None:
        self.summary_labels["analyzed"].setText(str(len(result.features)))
        self.summary_labels["suggested"].setText(str(len(result.suggestions)))
        self.summary_labels["duplicates"].setText(
            str(len(result.duplicate_pairs))
        )
        self.summary_labels["anomalies"].setText(
            str(result.anomaly_count)
        )
        self.summary_labels["loop"].setText(
            f"{result.loop_score * 100:.0f}%"
        )
        self.summary_labels["motion"].setText(
            f"{result.motion_total:.3f}"
        )

    def _clear_summary(self) -> None:
        for label in self.summary_labels.values():
            label.setText("—")
