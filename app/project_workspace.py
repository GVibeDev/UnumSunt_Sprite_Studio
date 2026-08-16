from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QAbstractItemView,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.project_store import (
    DIRECTIONS,
    GROUP_STATUSES,
    PROJECT_FILENAME,
    ProjectStore,
)


class ProjectWorkspace(QWidget):
    project_changed = Signal(str)
    save_requested = Signal()
    active_group_will_change = Signal(str, str)
    active_group_changed = Signal(str)
    status_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project_store: ProjectStore | None = None
        self._tree_items: dict[str, QTreeWidgetItem] = {}
        self._build_ui()
        self._refresh_view()

    @property
    def current_project_path(self) -> str | None:
        if self.project_store is None or self.project_store.path is None:
            return None
        return str(self.project_store.path.parent)

    @property
    def active_group_id(self) -> str | None:
        if self.project_store is None:
            return None
        group = self.project_store.get_active_group()
        return str(group['id']) if group else None

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        banner = QLabel(
            'R5e4 Project Groups — organizza la produzione come Soggetto → Animazione → Direzione. '
            'Solo una direzione può essere il gruppo attivo della pipeline.'
        )
        banner.setWordWrap(True)
        banner.setStyleSheet('QLabel { color: #f4f6f8; padding: 9px; background: #20343a; border: 1px solid #4c7f88; }')
        root.addWidget(banner)

        actions = QHBoxLayout()
        self.new_button = QPushButton('Nuovo progetto')
        self.new_button.clicked.connect(self._create_project_interactive)
        self.open_button = QPushButton('Apri progetto')
        self.open_button.clicked.connect(self._open_project_interactive)
        self.save_button = QPushButton('Salva metadati progetto')
        self.save_button.clicked.connect(self.save_project_metadata)
        self.snapshot_button = QPushButton('Salva snapshot pipeline')
        self.snapshot_button.clicked.connect(self.save_requested.emit)
        actions.addWidget(self.new_button)
        actions.addWidget(self.open_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.snapshot_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.active_group_label = QLabel('Gruppo attivo: nessuno')
        self.active_group_label.setWordWrap(True)
        self.active_group_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #2b3325; border: 1px solid #64744f; font-weight: 600; }')
        root.addWidget(self.active_group_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 5, 0)

        groups_actions = QHBoxLayout()
        self.add_subject_button = QPushButton('+ Soggetto')
        self.add_subject_button.clicked.connect(self._add_subject)
        self.add_animation_button = QPushButton('+ Animazione')
        self.add_animation_button.clicked.connect(self._add_animation)
        self.add_direction_button = QPushButton('+ Direzione')
        self.add_direction_button.clicked.connect(self._add_direction)
        groups_actions.addWidget(self.add_subject_button)
        groups_actions.addWidget(self.add_animation_button)
        groups_actions.addWidget(self.add_direction_button)
        left_layout.addLayout(groups_actions)

        self.groups_tree = QTreeWidget()
        self.groups_tree.setColumnCount(4)
        self.groups_tree.setHeaderLabels(['Nome', 'Tipo', 'Stato', 'Aggiornato'])
        self.groups_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.groups_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.groups_tree.itemDoubleClicked.connect(lambda *_: self._set_selected_active())
        left_layout.addWidget(self.groups_tree, 1)

        item_actions = QHBoxLayout()
        self.activate_button = QPushButton('Imposta attivo')
        self.activate_button.clicked.connect(self._set_selected_active)
        self.rename_button = QPushButton('Rinomina')
        self.rename_button.clicked.connect(self._rename_selected)
        self.duplicate_button = QPushButton('Duplica')
        self.duplicate_button.clicked.connect(self._duplicate_selected)
        self.delete_button = QPushButton('Elimina')
        self.delete_button.clicked.connect(self._delete_selected)
        item_actions.addWidget(self.activate_button)
        item_actions.addWidget(self.rename_button)
        item_actions.addWidget(self.duplicate_button)
        item_actions.addWidget(self.delete_button)
        left_layout.addLayout(item_actions)

        copy_row = QHBoxLayout()
        self.copy_data_button = QPushButton('Copia dati da altra direzione…')
        self.copy_data_button.clicked.connect(self._copy_data_from_other_direction)
        copy_row.addWidget(self.copy_data_button)
        copy_row.addStretch(1)
        left_layout.addLayout(copy_row)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(5, 0, 0, 0)

        info_group = QGroupBox('Progetto corrente')
        info_form = QFormLayout(info_group)
        self.path_label = QLabel('Nessun progetto aperto')
        self.path_label.setWordWrap(True)
        self.name_edit = QLineEdit()
        self.subject_edit = QLineEdit()
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMaximumHeight(90)
        self.assets_label = QLabel('—')
        self.assets_label.setWordWrap(True)
        self.updated_label = QLabel('—')
        info_form.addRow('Cartella', self.path_label)
        info_form.addRow('Nome', self.name_edit)
        info_form.addRow('Soggetto legacy', self.subject_edit)
        info_form.addRow('Note', self.notes_edit)
        info_form.addRow('Asset globali', self.assets_label)
        info_form.addRow('Ultimo aggiornamento', self.updated_label)
        right_layout.addWidget(info_group)

        group_group = QGroupBox('Gruppo selezionato')
        group_form = QFormLayout(group_group)
        self.group_path_label = QLabel('—')
        self.group_path_label.setWordWrap(True)
        self.group_type_label = QLabel('—')
        self.group_status_combo = QComboBox()
        for status in GROUP_STATUSES:
            self.group_status_combo.addItem(status.replace('_', ' ').title(), status)
        self.group_notes_edit = QPlainTextEdit()
        self.group_notes_edit.setMaximumHeight(120)
        self.group_assets_label = QLabel('—')
        self.group_assets_label.setWordWrap(True)
        self.group_counts_label = QLabel('—')
        self.group_counts_label.setWordWrap(True)
        save_group_button = QPushButton('Salva stato e note gruppo')
        save_group_button.clicked.connect(self._save_selected_group_details)
        group_form.addRow('Percorso', self.group_path_label)
        group_form.addRow('Tipo', self.group_type_label)
        group_form.addRow('Stato', self.group_status_combo)
        group_form.addRow('Note', self.group_notes_edit)
        group_form.addRow('Asset', self.group_assets_label)
        group_form.addRow('Dati', self.group_counts_label)
        group_form.addRow('', save_group_button)
        right_layout.addWidget(group_group)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([850, 550])

    def _selected_group_id(self) -> str | None:
        items = self.groups_tree.selectedItems()
        if not items:
            return None
        value = items[0].data(0, Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _refresh_view(self, select_group_id: str | None = None) -> None:
        has_project = self.project_store is not None
        for widget in (
            self.save_button, self.snapshot_button, self.add_subject_button, self.add_animation_button,
            self.add_direction_button, self.groups_tree,
        ):
            widget.setEnabled(has_project)
        if not has_project:
            self.path_label.setText('Nessun progetto aperto')
            self.name_edit.setText('')
            self.subject_edit.setText('')
            self.notes_edit.setPlainText('')
            self.assets_label.setText('—')
            self.updated_label.setText('—')
            self.groups_tree.clear()
            self.active_group_label.setText('Gruppo attivo: nessuno')
            self._refresh_selected_group_details()
            return

        payload = self.project_store.load()
        self.path_label.setText(str(self.project_store.path.parent))
        self.name_edit.setText(str(payload.get('name', '')))
        self.subject_edit.setText(str(payload.get('subject', '')))
        self.notes_edit.setPlainText(str(payload.get('notes', '')))
        assets = payload.get('assets', {}) if isinstance(payload.get('assets'), dict) else {}
        asset_lines = [f'{key}: {Path(str(value)).name}' for key, value in assets.items() if value]
        self.assets_label.setText('\n'.join(asset_lines) if asset_lines else 'Nessun asset globale registrato.')
        self.updated_label.setText(str(payload.get('updated_at', '—')))
        self._populate_groups_tree(payload, select_group_id=select_group_id)
        active_id = payload.get('active_group_id')
        if active_id:
            try:
                self.active_group_label.setText(f'Gruppo attivo: {self.project_store.group_label(active_id)}')
            except Exception:
                self.active_group_label.setText('Gruppo attivo: non valido')
        else:
            self.active_group_label.setText('Gruppo attivo: nessuno')
        self._refresh_selected_group_details()

    def _populate_groups_tree(self, payload: dict, *, select_group_id: str | None = None) -> None:
        self.groups_tree.clear()
        self._tree_items.clear()
        groups = payload.get('groups', []) if isinstance(payload.get('groups'), list) else []
        active_id = payload.get('active_group_id')
        children: dict[str | None, list[dict]] = {}
        for group in groups:
            children.setdefault(group.get('parent_id'), []).append(group)
        type_order = {'subject': 0, 'animation': 1, 'direction': 2}
        for bucket in children.values():
            bucket.sort(key=lambda g: (type_order.get(g.get('type'), 9), str(g.get('name', '')).lower()))

        def add_children(parent_id: str | None, parent_item: QTreeWidgetItem | None) -> None:
            for group in children.get(parent_id, []):
                name = str(group.get('name', 'Group'))
                if group.get('id') == active_id:
                    name = f'★ {name}'
                item = QTreeWidgetItem([
                    name,
                    str(group.get('type', '')),
                    str(group.get('status', '')),
                    str(group.get('updated_at', '')),
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, str(group.get('id')))
                if group.get('id') == active_id:
                    font = QFont(item.font(0))
                    font.setBold(True)
                    item.setFont(0, font)
                if parent_item is None:
                    self.groups_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                self._tree_items[str(group.get('id'))] = item
                add_children(str(group.get('id')), item)

        add_children(None, None)
        self.groups_tree.expandAll()
        target = select_group_id or active_id
        if target and target in self._tree_items:
            self.groups_tree.setCurrentItem(self._tree_items[target])

    def _refresh_selected_group_details(self) -> None:
        group_id = self._selected_group_id()
        if self.project_store is None or not group_id:
            self.group_path_label.setText('—')
            self.group_type_label.setText('—')
            self.group_notes_edit.setPlainText('')
            self.group_assets_label.setText('—')
            self.group_counts_label.setText('—')
            self.activate_button.setEnabled(False)
            self.rename_button.setEnabled(False)
            self.duplicate_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.copy_data_button.setEnabled(False)
            return
        group = self.project_store.get_group(group_id)
        if not group:
            return
        self.group_path_label.setText(self.project_store.group_label(group_id))
        self.group_type_label.setText(str(group['type']))
        status_index = self.group_status_combo.findData(str(group.get('status', 'missing')))
        if status_index >= 0:
            self.group_status_combo.setCurrentIndex(status_index)
        self.group_notes_edit.setPlainText(str(group.get('notes', '')))
        assets = group.get('assets', {}) if isinstance(group.get('assets'), dict) else {}
        asset_lines = [f'{key}: {Path(str(value)).name}' for key, value in assets.items() if value]
        self.group_assets_label.setText('\n'.join(asset_lines) if asset_lines else 'Nessun asset registrato.')
        self.group_counts_label.setText(
            f"Job: {len(group.get('jobs', []))} · Export: {len(group.get('exports', []))} · "
            f"Workspace: {group.get('workspace', '—')}"
        )
        is_direction = group['type'] == 'direction'
        self.activate_button.setEnabled(is_direction)
        self.rename_button.setEnabled(True)
        self.duplicate_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.copy_data_button.setEnabled(is_direction)

    def _on_tree_selection_changed(self) -> None:
        self._refresh_selected_group_details()

    def load_project_path(self, path: str) -> None:
        try:
            self.project_store = ProjectStore.open(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, 'Errore progetto', str(exc))
            return
        self._refresh_view()
        current = self.current_project_path
        if current:
            self.project_changed.emit(current)
            active = self.active_group_id
            if active:
                self.active_group_changed.emit(active)
            self.status_message.emit(f'Progetto aperto: {current}')

    def _create_project_interactive(self) -> None:
        if self.project_store is not None:
            self.save_requested.emit()
        project_dir = QFileDialog.getExistingDirectory(self, 'Seleziona cartella del nuovo progetto')
        if not project_dir:
            return
        suggested_name = Path(project_dir).name
        self.project_store = ProjectStore.create(Path(project_dir), name=suggested_name)
        self._refresh_view()
        current = self.current_project_path
        if current:
            self.project_changed.emit(current)
            self.status_message.emit(f'Nuovo progetto creato: {current}')

    def _open_project_interactive(self) -> None:
        if self.project_store is not None:
            self.save_requested.emit()
        selected_dir = QFileDialog.getExistingDirectory(self, 'Apri cartella progetto')
        if not selected_dir:
            return
        target = Path(selected_dir)
        if not (target / PROJECT_FILENAME).exists():
            QMessageBox.warning(self, 'Progetto non valido', f'File {PROJECT_FILENAME} non trovato in {target}.')
            return
        self.load_project_path(str(target))

    def save_project_metadata(self) -> None:
        if self.project_store is None:
            return
        payload = self.project_store.load()
        payload['name'] = self.name_edit.text().strip() or payload.get('name') or self.project_store.path.parent.name
        payload['subject'] = self.subject_edit.text().strip()
        payload['notes'] = self.notes_edit.toPlainText().strip()
        self.project_store.save(payload)
        self._refresh_view(select_group_id=self._selected_group_id())
        self.status_message.emit('Metadati progetto salvati.')

    def update_project_snapshot(self, snapshot: dict) -> None:
        if self.project_store is None:
            return
        payload = self.project_store.load()
        payload['assets'] = snapshot.get('assets', payload.get('assets', {}))
        payload['pipeline_state'] = snapshot.get('pipeline_state', payload.get('pipeline_state', {}))
        jobs = snapshot.get('jobs')
        if isinstance(jobs, list):
            payload['jobs'] = jobs
        self.project_store.save(payload)
        self._refresh_view(select_group_id=self._selected_group_id())
        self.status_message.emit('Snapshot globale del progetto aggiornato.')

    def update_active_group_snapshot(self, snapshot: dict) -> None:
        if self.project_store is None or not self.active_group_id:
            return
        group_id = self.active_group_id
        self.project_store.update_group_snapshot(group_id, snapshot)
        self._refresh_view(select_group_id=group_id)
        self.status_message.emit(f'Snapshot salvato nel gruppo attivo: {self.project_store.group_label(group_id)}')

    def _add_subject(self) -> None:
        if self.project_store is None:
            return
        name, ok = QInputDialog.getText(self, 'Nuovo soggetto', 'Nome soggetto:')
        if not ok or not name.strip():
            return
        group = self.project_store.create_group(group_type='subject', name=name.strip())
        self._refresh_view(select_group_id=group['id'])

    def _add_animation(self) -> None:
        if self.project_store is None:
            return
        parent_id = self._selected_group_id()
        parent = self.project_store.get_group(parent_id) if parent_id else None
        if not parent or parent['type'] != 'subject':
            QMessageBox.information(self, 'Seleziona un soggetto', 'Per creare un’animazione seleziona prima un gruppo Soggetto.')
            return
        name, ok = QInputDialog.getText(self, 'Nuova animazione', 'Nome animazione (es. Walk, Idle, Run):')
        if not ok or not name.strip():
            return
        group = self.project_store.create_group(group_type='animation', name=name.strip(), parent_id=parent_id)
        self._refresh_view(select_group_id=group['id'])

    def _add_direction(self) -> None:
        if self.project_store is None:
            return
        parent_id = self._selected_group_id()
        parent = self.project_store.get_group(parent_id) if parent_id else None
        if not parent or parent['type'] != 'animation':
            QMessageBox.information(self, 'Seleziona un’animazione', 'Per creare una direzione seleziona prima un gruppo Animazione.')
            return
        direction, ok = QInputDialog.getItem(self, 'Nuova direzione', 'Direzione:', list(DIRECTIONS), 3, True)
        if not ok or not str(direction).strip():
            return
        name = str(direction).strip().upper()
        group = self.project_store.create_group(
            group_type='direction',
            name=name,
            parent_id=parent_id,
            metadata={'direction': name},
        )
        self._refresh_view(select_group_id=group['id'])

    def activate_group(self, group_id: str) -> None:
        if self.project_store is None:
            return
        group = self.project_store.get_group(group_id)
        if not group or group.get('type') != 'direction':
            raise ValueError('Solo un gruppo Direzione può essere attivato.')
        old_id = self.active_group_id or ''
        if old_id == group_id:
            self._refresh_view(select_group_id=group_id)
            return
        self.active_group_will_change.emit(old_id, group_id)
        self.project_store.set_active_group(group_id)
        self._refresh_view(select_group_id=group_id)
        self.active_group_changed.emit(group_id)
        self.status_message.emit(f'Gruppo attivo: {self.project_store.group_label(group_id)}')

    def _set_selected_active(self) -> None:
        if self.project_store is None:
            return
        group_id = self._selected_group_id()
        group = self.project_store.get_group(group_id) if group_id else None
        if not group or group['type'] != 'direction':
            return
        self.activate_group(group_id)

    def _rename_selected(self) -> None:
        if self.project_store is None:
            return
        group_id = self._selected_group_id()
        group = self.project_store.get_group(group_id) if group_id else None
        if not group:
            return
        name, ok = QInputDialog.getText(self, 'Rinomina gruppo', 'Nuovo nome:', text=str(group['name']))
        if not ok or not name.strip():
            return
        self.project_store.update_group(group_id, name=name.strip())
        self._refresh_view(select_group_id=group_id)

    def _duplicate_selected(self) -> None:
        if self.project_store is None:
            return
        group_id = self._selected_group_id()
        if not group_id:
            return
        clone = self.project_store.duplicate_group(group_id)
        self._refresh_view(select_group_id=clone['id'])
        self.status_message.emit('Gruppo duplicato con dati e sotto-gruppi.')

    def _delete_selected(self) -> None:
        if self.project_store is None:
            return
        group_id = self._selected_group_id()
        if not group_id:
            return
        label = self.project_store.group_label(group_id)
        answer = QMessageBox.question(self, 'Elimina gruppo', f'Eliminare "{label}" e tutti i suoi sotto-gruppi?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        old_active = self.active_group_id or ''
        self.project_store.delete_group(group_id)
        self._refresh_view()
        if old_active and self.active_group_id is None:
            self.active_group_changed.emit('')
        self.status_message.emit(f'Gruppo eliminato: {label}')

    def _copy_data_from_other_direction(self) -> None:
        if self.project_store is None:
            return
        target_id = self._selected_group_id()
        target = self.project_store.get_group(target_id) if target_id else None
        if not target or target['type'] != 'direction':
            return
        candidates = [group for group in self.project_store.list_groups() if group['type'] == 'direction' and group['id'] != target_id]
        if not candidates:
            QMessageBox.information(self, 'Nessuna sorgente', 'Non esistono altre direzioni da cui copiare i dati.')
            return
        labels = [self.project_store.group_label(group['id']) for group in candidates]
        selected, ok = QInputDialog.getItem(self, 'Copia dati produzione', 'Copia da:', labels, 0, False)
        if not ok:
            return
        source_id = candidates[labels.index(selected)]['id']
        answer = QMessageBox.question(
            self,
            'Conferma copia dati',
            'Questa operazione sostituisce asset, snapshot pipeline, job, export e stato del gruppo selezionato. Continuare?',
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.project_store.copy_group_data(source_id, target_id)
        self._refresh_view(select_group_id=target_id)
        if self.active_group_id == target_id:
            self.active_group_changed.emit(target_id)
        self.status_message.emit(f'Dati copiati da {selected}.')

    def _save_selected_group_details(self) -> None:
        if self.project_store is None:
            return
        group_id = self._selected_group_id()
        if not group_id:
            return
        self.project_store.update_group(
            group_id,
            status=str(self.group_status_combo.currentData()),
            notes=self.group_notes_edit.toPlainText().strip(),
        )
        self._refresh_view(select_group_id=group_id)
        self.status_message.emit('Stato e note gruppo salvati.')

    def append_job_to_active_group(self, job_payload: dict) -> None:
        if self.project_store is None or not self.active_group_id:
            return
        self.project_store.append_group_job(self.active_group_id, job_payload)
        self._refresh_view(select_group_id=self.active_group_id)

    def append_export_to_active_group(self, export_payload: dict) -> None:
        if self.project_store is None or not self.active_group_id:
            return
        self.project_store.append_group_export(self.active_group_id, export_payload)
        self._refresh_view(select_group_id=self.active_group_id)
