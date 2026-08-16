from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.character_sets import (
    DIRECTIONS,
    LAYER_KINDS,
    character_set_coverage,
    layer_assignment_coverage,
)
from app.project_store import ProjectStore


class CharacterSetWorkspace(QWidget):
    status_message = Signal(str)
    activate_group_requested = Signal(str)

    def __init__(
        self,
        *,
        project_store_provider: Callable[[], ProjectStore | None],
        active_group_id_provider: Callable[[], str | None],
    ) -> None:
        super().__init__()
        self._project_store_provider = project_store_provider
        self._active_group_id_provider = active_group_id_provider
        self._subject_ids: list[str] = []
        self._selected_direction_id: str | None = None
        self._build_ui()
        self.refresh_context()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        banner = QLabel(
            'R5e11 Character Set / Layer Manager — vista unificata Soggetto → Animazioni → 8 Direzioni. '
            'I layer sono non distruttivi: asset e offset vengono registrati per direzione senza alterare i frame base.'
        )
        banner.setWordWrap(True)
        banner.setStyleSheet('QLabel { color: #f4f6f8; padding: 9px; background: #28313c; border: 1px solid #596b80; }')
        root.addWidget(banner)

        top = QHBoxLayout()
        self.subject_combo = QComboBox()
        self.subject_combo.currentIndexChanged.connect(self._on_subject_changed)
        refresh_button = QPushButton('Aggiorna')
        refresh_button.clicked.connect(self.refresh_context)
        complete_button = QPushButton('Crea direzioni mancanti')
        complete_button.clicked.connect(self._create_missing_directions)
        top.addWidget(QLabel('Character Set'))
        top.addWidget(self.subject_combo, 1)
        top.addWidget(refresh_button)
        top.addWidget(complete_button)
        root.addLayout(top)

        self.summary_label = QLabel('—')
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #232c25; border: 1px solid #536657; }')
        root.addWidget(self.summary_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        coverage_box = QGroupBox('Copertura Character Set')
        coverage_layout = QVBoxLayout(coverage_box)
        self.coverage_table = QTableWidget()
        self.coverage_table.setColumnCount(1 + len(DIRECTIONS))
        self.coverage_table.setHorizontalHeaderLabels(['Animazione', *DIRECTIONS])
        self.coverage_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.coverage_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.coverage_table.cellClicked.connect(self._on_coverage_cell_clicked)
        self.coverage_table.cellDoubleClicked.connect(self._activate_selected_direction)
        coverage_layout.addWidget(self.coverage_table)
        coverage_actions = QHBoxLayout()
        self.activate_direction_button = QPushButton('Attiva direzione selezionata')
        self.activate_direction_button.clicked.connect(self._activate_selected_direction)
        coverage_actions.addWidget(self.activate_direction_button)
        coverage_actions.addStretch(1)
        coverage_layout.addLayout(coverage_actions)
        splitter.addWidget(coverage_box)

        lower = QSplitter(Qt.Orientation.Horizontal)
        lower.setChildrenCollapsible(False)

        layers_box = QGroupBox('Layer logici del soggetto')
        layers_layout = QVBoxLayout(layers_box)
        self.layers_table = QTableWidget()
        self.layers_table.setColumnCount(7)
        self.layers_table.setHorizontalHeaderLabels(['#', 'Nome', 'Tipo', 'On', 'Export', 'Opacità', 'Assegnazioni'])
        self.layers_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.layers_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.layers_table.itemSelectionChanged.connect(self._load_selected_layer_details)
        layers_layout.addWidget(self.layers_table, 1)
        layer_actions = QHBoxLayout()
        add_button = QPushButton('+ Layer')
        add_button.clicked.connect(self._add_layer)
        remove_button = QPushButton('Elimina')
        remove_button.clicked.connect(self._remove_layer)
        up_button = QPushButton('↑')
        up_button.clicked.connect(lambda: self._move_layer(-1))
        down_button = QPushButton('↓')
        down_button.clicked.connect(lambda: self._move_layer(1))
        layer_actions.addWidget(add_button)
        layer_actions.addWidget(remove_button)
        layer_actions.addWidget(up_button)
        layer_actions.addWidget(down_button)
        layer_actions.addStretch(1)
        layers_layout.addLayout(layer_actions)

        layer_form = QFormLayout()
        self.layer_name_label = QLabel('—')
        self.layer_kind_combo = QComboBox()
        for kind in LAYER_KINDS:
            self.layer_kind_combo.addItem(kind.title(), kind)
        self.layer_enabled_checkbox = QCheckBox('Abilitato nel Character Set')
        self.layer_export_checkbox = QCheckBox('Includi nel futuro export composito')
        self.layer_opacity_spin = QDoubleSpinBox()
        self.layer_opacity_spin.setRange(0.0, 1.0)
        self.layer_opacity_spin.setSingleStep(0.05)
        self.layer_opacity_spin.setDecimals(2)
        self.layer_notes_edit = QPlainTextEdit()
        self.layer_notes_edit.setMaximumHeight(70)
        save_layer_button = QPushButton('Salva proprietà layer')
        save_layer_button.clicked.connect(self._save_layer_details)
        layer_form.addRow('Layer', self.layer_name_label)
        layer_form.addRow('Tipo', self.layer_kind_combo)
        layer_form.addRow('', self.layer_enabled_checkbox)
        layer_form.addRow('', self.layer_export_checkbox)
        layer_form.addRow('Opacità', self.layer_opacity_spin)
        layer_form.addRow('Note', self.layer_notes_edit)
        layer_form.addRow('', save_layer_button)
        layers_layout.addLayout(layer_form)
        lower.addWidget(layers_box)

        assignment_box = QGroupBox('Asset layer per direzione')
        assignment_layout = QVBoxLayout(assignment_box)
        self.direction_label = QLabel('Direzione: nessuna')
        self.direction_label.setWordWrap(True)
        assignment_layout.addWidget(self.direction_label)
        self.assignment_layer_combo = QComboBox()
        self.assignment_layer_combo.currentIndexChanged.connect(self._load_assignment_details)
        assignment_layout.addWidget(self.assignment_layer_combo)

        assign_actions = QHBoxLayout()
        import_file_button = QPushButton('Importa PNG/WebP')
        import_file_button.clicked.connect(self._import_layer_file)
        import_sequence_button = QPushButton('Importa sequenza…')
        import_sequence_button.clicked.connect(self._import_layer_sequence)
        remove_asset_button = QPushButton('Rimuovi asset')
        remove_asset_button.clicked.connect(self._remove_layer_asset)
        assign_actions.addWidget(import_file_button)
        assign_actions.addWidget(import_sequence_button)
        assign_actions.addWidget(remove_asset_button)
        assignment_layout.addLayout(assign_actions)

        assignment_form = QFormLayout()
        self.assignment_info_label = QLabel('—')
        self.assignment_info_label.setWordWrap(True)
        self.assignment_visible_checkbox = QCheckBox('Visibile')
        self.assignment_offset_x = QSpinBox()
        self.assignment_offset_x.setRange(-4096, 4096)
        self.assignment_offset_y = QSpinBox()
        self.assignment_offset_y.setRange(-4096, 4096)
        save_assignment_button = QPushButton('Salva offset / visibilità')
        save_assignment_button.clicked.connect(self._save_assignment_details)
        assignment_form.addRow('Asset', self.assignment_info_label)
        assignment_form.addRow('', self.assignment_visible_checkbox)
        assignment_form.addRow('Offset X', self.assignment_offset_x)
        assignment_form.addRow('Offset Y', self.assignment_offset_y)
        assignment_form.addRow('', save_assignment_button)
        assignment_layout.addLayout(assignment_form)
        assignment_note = QLabel(
            'I file vengono copiati nel workspace della direzione in layers/<layer_id>/. '
            'R5e11 non appiattisce né modifica i frame base: prepara uno stack riutilizzabile dalle milestone successive.'
        )
        assignment_note.setWordWrap(True)
        assignment_note.setStyleSheet('color: #9aa1ad;')
        assignment_layout.addWidget(assignment_note)
        assignment_layout.addStretch(1)
        lower.addWidget(assignment_box)
        lower.setStretchFactor(0, 3)
        lower.setStretchFactor(1, 2)
        splitter.addWidget(lower)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

    def _store(self) -> ProjectStore | None:
        return self._project_store_provider()

    def _current_subject_id(self) -> str | None:
        index = self.subject_combo.currentIndex()
        if index < 0:
            return None
        value = self.subject_combo.itemData(index)
        return str(value) if value else None

    def _selected_layer_id(self) -> str | None:
        rows = self.layers_table.selectionModel().selectedRows() if self.layers_table.selectionModel() else []
        if not rows:
            return None
        item = self.layers_table.item(rows[0].row(), 1)
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return str(value) if value else None

    def refresh_context(self) -> None:
        store = self._store()
        current_subject = self._current_subject_id()
        preferred: str | None = current_subject
        if store is not None:
            active = self._active_group_id_provider()
            if active:
                try:
                    preferred = store.subject_for_group(active)['id']
                except Exception:
                    pass
        self.subject_combo.blockSignals(True)
        self.subject_combo.clear()
        self._subject_ids = []
        if store is not None:
            for group in store.list_groups():
                if group.get('type') == 'subject':
                    self.subject_combo.addItem(str(group.get('name')), str(group.get('id')))
                    self._subject_ids.append(str(group.get('id')))
        if preferred:
            index = self.subject_combo.findData(preferred)
            if index >= 0:
                self.subject_combo.setCurrentIndex(index)
        self.subject_combo.blockSignals(False)
        self._refresh_subject_view()

    def _on_subject_changed(self, _index: int) -> None:
        self._selected_direction_id = None
        self._refresh_subject_view()

    def _refresh_subject_view(self) -> None:
        store = self._store()
        subject_id = self._current_subject_id()
        self.coverage_table.setRowCount(0)
        self.layers_table.setRowCount(0)
        self.assignment_layer_combo.clear()
        self._selected_direction_id = None
        self.direction_label.setText('Direzione: nessuna')
        if store is None or not subject_id:
            self.summary_label.setText('Apri un progetto con almeno un gruppo Soggetto.')
            return
        groups = store.list_groups()
        coverage = character_set_coverage(groups, subject_id)
        self.summary_label.setText(
            f"{coverage['subject']} · {coverage['animation_count']} animazioni · "
            f"direzioni presenti {coverage['present_slots']}/{coverage['total_slots']} "
            f"({coverage['coverage_percent']:.0f}%) · pronte/allineate {coverage['ready_slots']} "
            f"({coverage['ready_percent']:.0f}%)"
        )
        self.coverage_table.setRowCount(len(coverage['rows']))
        for row_index, row in enumerate(coverage['rows']):
            animation_item = QTableWidgetItem(row['animation'])
            animation_item.setData(Qt.ItemDataRole.UserRole, row['animation_id'])
            self.coverage_table.setItem(row_index, 0, animation_item)
            for col_index, cell in enumerate(row['directions'], start=1):
                text = '—' if not cell['present'] else str(cell['status']).replace('_', ' ')
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, cell['group_id'])
                item.setToolTip(f"{cell['direction']} · {cell['status']}")
                self.coverage_table.setItem(row_index, col_index, item)
        self.coverage_table.resizeColumnsToContents()

        state = store.get_character_set(subject_id)
        layer_ids = [layer['id'] for layer in state['layers']]
        assignment_coverage = layer_assignment_coverage(groups, subject_id, layer_ids)
        self.layers_table.setRowCount(len(state['layers']))
        for row, layer in enumerate(state['layers']):
            values = [
                str(row + 1), str(layer['name']), str(layer['kind']),
                '✓' if layer['enabled'] else '—',
                '✓' if layer['export_enabled'] else '—',
                f"{float(layer['opacity']):.2f}",
                f"{assignment_coverage['assigned_by_layer'].get(layer['id'], 0)}/{assignment_coverage['direction_count']}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 1:
                    item.setData(Qt.ItemDataRole.UserRole, layer['id'])
                self.layers_table.setItem(row, col, item)
        self.layers_table.resizeColumnsToContents()
        for layer in state['layers']:
            self.assignment_layer_combo.addItem(str(layer['name']), str(layer['id']))
        active = self._active_group_id_provider()
        if active:
            group = store.get_group(active)
            if group and group.get('type') == 'direction':
                try:
                    if store.subject_for_group(active)['id'] == subject_id:
                        self._selected_direction_id = active
                        self.direction_label.setText(f"Direzione: {store.group_label(active)}")
                except Exception:
                    pass
        self._load_assignment_details()

    def _on_coverage_cell_clicked(self, row: int, column: int) -> None:
        if column <= 0:
            return
        item = self.coverage_table.item(row, column)
        group_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._selected_direction_id = str(group_id) if group_id else None
        store = self._store()
        if store and self._selected_direction_id:
            self.direction_label.setText(f'Direzione: {store.group_label(self._selected_direction_id)}')
        else:
            self.direction_label.setText('Direzione: slot non creato')
        self._load_assignment_details()

    def _activate_selected_direction(self, *_args) -> None:
        if self._selected_direction_id:
            self.activate_group_requested.emit(self._selected_direction_id)

    def _create_missing_directions(self) -> None:
        store = self._store()
        subject_id = self._current_subject_id()
        if store is None or not subject_id:
            return
        groups = store.list_groups()
        animation_ids = [g['id'] for g in groups if g.get('type') == 'animation' and g.get('parent_id') == subject_id]
        if not animation_ids:
            QMessageBox.information(self, 'Nessuna animazione', 'Creare prima almeno un gruppo Animazione nel progetto.')
            return
        created = 0
        for animation_id in animation_ids:
            children = [g for g in store.list_groups() if g.get('type') == 'direction' and g.get('parent_id') == animation_id]
            present = {str((g.get('metadata') or {}).get('direction') or g.get('name') or '').upper() for g in children}
            for direction in DIRECTIONS:
                if direction in present:
                    continue
                store.create_group(group_type='direction', name=direction, parent_id=animation_id, metadata={'direction': direction})
                created += 1
        self.refresh_context()
        self.status_message.emit(f'R5e11: create {created} direzioni mancanti nel Character Set.')

    def _add_layer(self) -> None:
        store = self._store()
        subject_id = self._current_subject_id()
        if store is None or not subject_id:
            return
        name, ok = QInputDialog.getText(self, 'Nuovo layer', 'Nome layer (es. Mantello, Arma, Effetti):')
        if not ok or not name.strip():
            return
        kind, ok = QInputDialog.getItem(self, 'Tipo layer', 'Tipo:', list(LAYER_KINDS), 1, False)
        if not ok:
            return
        layer = store.add_character_layer(subject_id, name.strip(), kind=str(kind))
        self._refresh_subject_view()
        self._select_layer(layer['id'])

    def _select_layer(self, layer_id: str) -> None:
        for row in range(self.layers_table.rowCount()):
            item = self.layers_table.item(row, 1)
            if item and str(item.data(Qt.ItemDataRole.UserRole)) == layer_id:
                self.layers_table.selectRow(row)
                return

    def _remove_layer(self) -> None:
        store = self._store()
        subject_id = self._current_subject_id()
        layer_id = self._selected_layer_id()
        if store is None or not subject_id or not layer_id:
            return
        answer = QMessageBox.question(
            self, 'Elimina layer',
            'Eliminare il layer dal Character Set e tutte le sue assegnazioni nelle direzioni? I frame base non verranno modificati.'
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        store.remove_character_layer(subject_id, layer_id)
        self._refresh_subject_view()

    def _move_layer(self, delta: int) -> None:
        store = self._store()
        subject_id = self._current_subject_id()
        layer_id = self._selected_layer_id()
        if store is None or not subject_id or not layer_id:
            return
        store.move_character_layer(subject_id, layer_id, delta)
        self._refresh_subject_view()
        self._select_layer(layer_id)

    def _load_selected_layer_details(self) -> None:
        store = self._store()
        subject_id = self._current_subject_id()
        layer_id = self._selected_layer_id()
        if store is None or not subject_id or not layer_id:
            self.layer_name_label.setText('—')
            return
        state = store.get_character_set(subject_id)
        layer = next((layer for layer in state['layers'] if layer['id'] == layer_id), None)
        if not layer:
            return
        self.layer_name_label.setText(str(layer['name']))
        index = self.layer_kind_combo.findData(layer['kind'])
        if index >= 0:
            self.layer_kind_combo.setCurrentIndex(index)
        self.layer_enabled_checkbox.setChecked(bool(layer['enabled']))
        self.layer_export_checkbox.setChecked(bool(layer['export_enabled']))
        self.layer_opacity_spin.setValue(float(layer['opacity']))
        self.layer_notes_edit.setPlainText(str(layer['notes']))

    def _save_layer_details(self) -> None:
        store = self._store()
        subject_id = self._current_subject_id()
        layer_id = self._selected_layer_id()
        if store is None or not subject_id or not layer_id:
            return
        store.update_character_layer(
            subject_id, layer_id,
            kind=str(self.layer_kind_combo.currentData()),
            enabled=self.layer_enabled_checkbox.isChecked(),
            export_enabled=self.layer_export_checkbox.isChecked(),
            opacity=self.layer_opacity_spin.value(),
            notes=self.layer_notes_edit.toPlainText().strip(),
        )
        self._refresh_subject_view()
        self._select_layer(layer_id)
        self.status_message.emit('Proprietà layer salvate.')

    def _assignment_layer_id(self) -> str | None:
        value = self.assignment_layer_combo.currentData()
        return str(value) if value else None

    def _import_layer_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Importa asset layer', '', 'Layer raster (*.png *.webp)')
        if path:
            self._import_layer_source(Path(path))

    def _import_layer_sequence(self) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Importa cartella sequenza layer')
        if path:
            self._import_layer_source(Path(path))

    def _import_layer_source(self, source: Path) -> None:
        store = self._store()
        layer_id = self._assignment_layer_id()
        if store is None or not self._selected_direction_id or not layer_id:
            QMessageBox.information(self, 'Direzione/layer mancanti', 'Seleziona una direzione esistente e un layer.')
            return
        try:
            assignment = store.import_direction_layer_asset(self._selected_direction_id, layer_id, source)
        except Exception as exc:
            QMessageBox.warning(self, 'Import layer non riuscito', str(exc))
            return
        self._load_assignment_details()
        self._refresh_subject_view()
        self.status_message.emit(
            f"Layer importato: {assignment['frame_count']} frame · {assignment['width']}×{assignment['height']}"
        )

    def _remove_layer_asset(self) -> None:
        store = self._store()
        layer_id = self._assignment_layer_id()
        if store is None or not self._selected_direction_id or not layer_id:
            return
        store.remove_direction_layer_asset(self._selected_direction_id, layer_id)
        self._load_assignment_details()
        self._refresh_subject_view()

    def _load_assignment_details(self) -> None:
        store = self._store()
        layer_id = self._assignment_layer_id()
        if store is None or not self._selected_direction_id or not layer_id:
            self.assignment_info_label.setText('Nessun asset assegnato.')
            self.assignment_visible_checkbox.setChecked(False)
            self.assignment_offset_x.setValue(0)
            self.assignment_offset_y.setValue(0)
            return
        try:
            stack = store.get_direction_layer_stack(self._selected_direction_id)
        except Exception:
            return
        assignment = stack['assignments'].get(layer_id)
        if not assignment:
            self.assignment_info_label.setText('Nessun asset assegnato.')
            self.assignment_visible_checkbox.setChecked(False)
            self.assignment_offset_x.setValue(0)
            self.assignment_offset_y.setValue(0)
            return
        alpha = 'alpha' if assignment.get('has_alpha') else 'opaco'
        self.assignment_info_label.setText(
            f"{assignment.get('mode')} · {assignment.get('frame_count')} frame · "
            f"{assignment.get('width')}×{assignment.get('height')} · {alpha}\n"
            f"{Path(str(assignment.get('manifest_path'))).name}"
        )
        self.assignment_visible_checkbox.setChecked(bool(assignment.get('visible', True)))
        self.assignment_offset_x.setValue(int(assignment.get('offset_x') or 0))
        self.assignment_offset_y.setValue(int(assignment.get('offset_y') or 0))

    def _save_assignment_details(self) -> None:
        store = self._store()
        layer_id = self._assignment_layer_id()
        if store is None or not self._selected_direction_id or not layer_id:
            return
        try:
            store.update_direction_layer_assignment(
                self._selected_direction_id, layer_id,
                visible=self.assignment_visible_checkbox.isChecked(),
                offset_x=self.assignment_offset_x.value(),
                offset_y=self.assignment_offset_y.value(),
            )
        except KeyError:
            QMessageBox.information(self, 'Asset non assegnato', 'Importa prima un asset per questo layer e direzione.')
            return
        self._load_assignment_details()
        self.status_message.emit('Offset e visibilità del layer salvati.')
