from __future__ import annotations

from copy import deepcopy
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.workflows import (
    WORKFLOW_DEFINITIONS,
    new_workflow_state,
    now_iso,
    next_incomplete_step,
    normalize_workflow_state,
    set_step_state,
    step_statuses,
    workflow_definition,
)


class WorkflowWorkspace(QWidget):
    status_message = Signal(str)
    route_requested = Signal(str)
    guided_tabs_changed = Signal(bool)
    settings_checkpoint_requested = Signal()
    motion_reference_requested = Signal()

    def __init__(
        self,
        *,
        project_store_provider: Callable[[], object | None],
        active_group_id_provider: Callable[[], str | None],
    ) -> None:
        super().__init__()
        self._project_store_provider = project_store_provider
        self._active_group_id_provider = active_group_id_provider
        self._build_ui()
        self.refresh_context()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        title = QLabel('R5e10 · Guided Workflows / Workflow Router')
        title.setStyleSheet('font-size: 20px; font-weight: 700;')
        root.addWidget(title)
        intro = QLabel(
            'Sprite Studio organizza gli strumenti già validati in tre percorsi produttivi. '
            'Il workflow non blocca i dati: registra il percorso del Project Group e guida verso il prossimo step.'
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        choose_group = QGroupBox('Workflow del Project Group attivo')
        choose_layout = QVBoxLayout(choose_group)
        row = QHBoxLayout()
        self.workflow_combo = QComboBox()
        for workflow_type, definition in WORKFLOW_DEFINITIONS.items():
            self.workflow_combo.addItem(definition['title'], workflow_type)
        self.apply_workflow_button = QPushButton('Imposta / cambia workflow')
        self.apply_workflow_button.clicked.connect(self._apply_workflow)
        row.addWidget(self.workflow_combo, 1)
        row.addWidget(self.apply_workflow_button)
        choose_layout.addLayout(row)
        self.workflow_description = QLabel('')
        self.workflow_description.setWordWrap(True)
        self.workflow_description.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #252a30; border: 1px solid #4b5560; }')
        choose_layout.addWidget(self.workflow_description)
        self.guided_tabs_checkbox = QCheckBox('Vista guidata: mostra soltanto i workspace pertinenti al workflow')
        self.guided_tabs_checkbox.toggled.connect(self._guided_tabs_toggled)
        choose_layout.addWidget(self.guided_tabs_checkbox)
        root.addWidget(choose_group)

        steps_group = QGroupBox('Percorso operativo')
        steps_layout = QVBoxLayout(steps_group)
        self.group_label = QLabel('Nessun Project Group attivo.')
        self.group_label.setWordWrap(True)
        self.group_label.setStyleSheet('font-weight: 600;')
        steps_layout.addWidget(self.group_label)
        self.step_list = QListWidget()
        self.step_list.currentItemChanged.connect(self._on_step_selected)
        steps_layout.addWidget(self.step_list, 1)

        actions = QHBoxLayout()
        self.open_step_button = QPushButton('Apri step')
        self.open_step_button.clicked.connect(self._open_step)
        self.complete_button = QPushButton('Segna completato')
        self.complete_button.clicked.connect(lambda: self._set_selected_step('complete'))
        self.pending_button = QPushButton('Riapri step')
        self.pending_button.clicked.connect(lambda: self._set_selected_step('pending'))
        self.skip_button = QPushButton('Salta step')
        self.skip_button.clicked.connect(lambda: self._set_selected_step('skipped'))
        actions.addWidget(self.open_step_button)
        actions.addWidget(self.complete_button)
        actions.addWidget(self.pending_button)
        actions.addWidget(self.skip_button)
        steps_layout.addLayout(actions)

        special = QHBoxLayout()
        self.checkpoint_button = QPushButton('Salva checkpoint impostazioni')
        self.checkpoint_button.clicked.connect(self.settings_checkpoint_requested.emit)
        self.motion_reference_button = QPushButton('Usa video corrente come riferimento movimento')
        self.motion_reference_button.clicked.connect(self.motion_reference_requested.emit)
        special.addWidget(self.checkpoint_button)
        special.addWidget(self.motion_reference_button)
        steps_layout.addLayout(special)

        self.step_help = QTextEdit()
        self.step_help.setReadOnly(True)
        self.step_help.setMaximumHeight(145)
        steps_layout.addWidget(self.step_help)
        root.addWidget(steps_group, 1)

        self.progress_label = QLabel('')
        self.progress_label.setWordWrap(True)
        self.progress_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 8px; background: #20382a; border: 1px solid #3d7b55; }')
        root.addWidget(self.progress_label)

        self.workflow_combo.currentIndexChanged.connect(self._preview_workflow_description)
        self._preview_workflow_description()

    def _store_and_group(self):
        store = self._project_store_provider()
        group_id = self._active_group_id_provider()
        if store is None or not group_id:
            return None, None, None
        group = store.get_group(group_id)
        return store, group_id, group

    def _preview_workflow_description(self) -> None:
        workflow_type = str(self.workflow_combo.currentData() or '')
        definition = WORKFLOW_DEFINITIONS.get(workflow_type)
        self.workflow_description.setText(definition['description'] if definition else '')

    def current_workflow(self) -> dict | None:
        store, group_id, group = self._store_and_group()
        if store is None or not group_id or group is None:
            return None
        metadata = group.get('metadata') if isinstance(group.get('metadata'), dict) else {}
        return normalize_workflow_state(metadata.get('workflow'))

    def current_workflow_type(self) -> str | None:
        workflow = self.current_workflow()
        return str(workflow['type']) if workflow else None

    def _apply_workflow(self) -> None:
        store, group_id, group = self._store_and_group()
        if store is None or not group_id or group is None:
            QMessageBox.information(self, 'Nessun gruppo', 'Attivare prima un Project Group di direzione.')
            return
        workflow_type = str(self.workflow_combo.currentData())
        existing = self.current_workflow()
        if existing and existing.get('type') != workflow_type:
            answer = QMessageBox.question(
                self,
                'Cambia workflow',
                'Cambiare workflow conserva asset e pipeline ma azzera il progresso guidato specifico del workflow. Continuare?',
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if existing and existing.get('type') == workflow_type:
            state = existing
        else:
            state = new_workflow_state(workflow_type)
        store.set_group_workflow(group_id, state)
        self.status_message.emit(f'Workflow impostato: {workflow_definition(workflow_type)["title"]}')
        self.refresh_context()
        self.guided_tabs_changed.emit(bool(state.get('guided_tabs', False)))

    def _save_workflow(self, workflow: dict) -> None:
        store, group_id, group = self._store_and_group()
        if store is None or not group_id or group is None:
            return
        store.set_group_workflow(group_id, workflow)

    def _guided_tabs_toggled(self, checked: bool) -> None:
        workflow = self.current_workflow()
        if workflow is None:
            return
        workflow['guided_tabs'] = bool(checked)
        self._save_workflow(workflow)
        self.guided_tabs_changed.emit(bool(checked))
        self.status_message.emit('Vista guidata aggiornata.')

    def _selected_step_id(self) -> str | None:
        item = self.step_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _selected_step(self) -> dict | None:
        workflow = self.current_workflow()
        step_id = self._selected_step_id()
        if workflow is None or not step_id:
            return None
        for row in step_statuses(self._store_and_group()[2], workflow):
            if row['id'] == step_id:
                return row
        return None

    def _open_step(self) -> None:
        step = self._selected_step()
        if step is None:
            return
        workflow = self.current_workflow()
        if workflow is not None:
            workflow['current_step'] = step['id']
            self._save_workflow(workflow)
        self.route_requested.emit(str(step['route']))
        self.refresh_context(select_step_id=str(step['id']))

    def _set_selected_step(self, state: str) -> None:
        workflow = self.current_workflow()
        step_id = self._selected_step_id()
        if workflow is None or not step_id:
            return
        workflow = set_step_state(workflow, step_id, state)
        store, group_id, group = self._store_and_group()
        if group is not None:
            next_step = next_incomplete_step(group, workflow)
            if next_step:
                workflow['current_step'] = next_step
        self._save_workflow(workflow)
        self.refresh_context(select_step_id=step_id)

    def _on_step_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            self.step_help.clear()
            return
        step_id = str(current.data(Qt.ItemDataRole.UserRole))
        workflow = self.current_workflow()
        if workflow is None:
            return
        definition = workflow_definition(workflow['type'])
        position = next((i for i, step in enumerate(definition['steps']) if step['id'] == step_id), None)
        if position is None:
            return
        step = definition['steps'][position]
        hints = {
            'video_generation': 'Apri Genera, verifica reference image e motion reference già pronti, quindi lancia WAN.',
            'image_generation': 'Apri Image Generator. Genera il master da prompt: R5e9 lo caricherà automaticamente come reference WAN.',
            'spritesheet_import': 'Apri Sprite Sheet. Importa/decomponi l’animazione desiderata e prepara i frame o la reference sheet necessaria.',
            'motion_reference': 'Dopo aver generato il video intermedio che rappresenta il movimento, torna qui e usa “Usa video corrente come riferimento movimento”. Il master R5e9 viene ripristinato come reference finale.',
            'final_video_generation': 'In Genera devono essere presenti il master image e il video di movimento. Lancia la generazione finale.',
            'frame_selection': 'In Estrazione R1 scegli i frame utili. Smart Selection resta disponibile come supporto.',
            'cleanup': 'Applica chroma/alpha, clean-up manuale e propagazione dove necessario.',
            'alignment': 'Allinea pivot e geometria; nel workflow spritesheet qui rientrano anche up/downscaling e output geometry.',
            'settings_checkpoint': 'Salva uno snapshot esplicito delle impostazioni correnti del gruppo con il pulsante dedicato.',
            'export': 'Apri Export Studio ed esporta singoli frame e/o spritesheet finale.',
        }
        self.step_help.setPlainText(hints.get(step_id, step['title']))

    def refresh_context(self, *, select_step_id: str | None = None) -> None:
        store, group_id, group = self._store_and_group()
        has_group = store is not None and group_id is not None and group is not None
        self.apply_workflow_button.setEnabled(has_group)
        self.step_list.clear()
        if not has_group:
            self.group_label.setText('Nessun Project Group di direzione attivo.')
            self.progress_label.setText('Attiva un gruppo in Progetto per scegliere il workflow.')
            self.guided_tabs_checkbox.setEnabled(False)
            self.checkpoint_button.setEnabled(False)
            self.motion_reference_button.setEnabled(False)
            return

        self.group_label.setText(f'Gruppo attivo: {store.group_label(group_id)}')
        workflow = self.current_workflow()
        if workflow is None:
            self.progress_label.setText('Workflow non ancora scelto. Seleziona uno dei tre flussi ufficiali.')
            self.guided_tabs_checkbox.setEnabled(False)
            self.checkpoint_button.setEnabled(False)
            self.motion_reference_button.setEnabled(False)
            return

        combo_index = self.workflow_combo.findData(workflow['type'])
        if combo_index >= 0:
            self.workflow_combo.blockSignals(True)
            self.workflow_combo.setCurrentIndex(combo_index)
            self.workflow_combo.blockSignals(False)
        self._preview_workflow_description()
        self.guided_tabs_checkbox.setEnabled(True)
        self.guided_tabs_checkbox.blockSignals(True)
        self.guided_tabs_checkbox.setChecked(bool(workflow.get('guided_tabs', False)))
        self.guided_tabs_checkbox.blockSignals(False)

        rows = step_statuses(group, workflow)
        status_icons = {'complete': '✓', 'current': '▶', 'pending': '○', 'skipped': '↷'}
        selected_item = None
        for row in rows:
            item = QListWidgetItem(f"{status_icons[row['status']]}  {row['index'] + 1}. {row['title']}")
            item.setData(Qt.ItemDataRole.UserRole, row['id'])
            if row['status'] == 'complete':
                item.setToolTip('Completato (automaticamente o manualmente).')
            elif row['status'] == 'skipped':
                item.setToolTip('Saltato esplicitamente.')
            self.step_list.addItem(item)
            if select_step_id == row['id'] or (select_step_id is None and row['id'] == workflow.get('current_step')):
                selected_item = item
        if selected_item is not None:
            self.step_list.setCurrentItem(selected_item)
        elif self.step_list.count():
            self.step_list.setCurrentRow(0)

        completed_count = sum(1 for row in rows if row['status'] in {'complete', 'skipped'})
        self.progress_label.setText(
            f"{workflow_definition(workflow['type'])['title']} · {completed_count}/{len(rows)} step conclusi. "
            f"Prossimo: {next_incomplete_step(group, workflow) or 'workflow completato'}."
        )
        self.checkpoint_button.setEnabled(True)
        self.motion_reference_button.setEnabled(workflow['type'] == 'full')

    def record_settings_checkpoint(self, pipeline_state: dict) -> None:
        workflow = self.current_workflow()
        if workflow is None:
            return
        checkpoints = workflow.setdefault('settings_checkpoints', [])
        checkpoints.append({
            'id': f'checkpoint_{len(checkpoints) + 1:03d}',
            'created_at': now_iso(),
            'pipeline_state': deepcopy(pipeline_state),
        })
        workflow = set_step_state(workflow, 'settings_checkpoint', 'complete')
        self._save_workflow(workflow)
        self.refresh_context(select_step_id='settings_checkpoint')
        self.status_message.emit('Checkpoint impostazioni salvato nel Project Group.')

    def record_motion_reference(self, *, path: str, promoted_from_source_video: str) -> None:
        workflow = self.current_workflow()
        if workflow is None or workflow.get('type') != 'full':
            return
        workflow['motion_reference'] = {
            'path': str(path),
            'promoted_from_source_video': str(promoted_from_source_video),
        }
        workflow = set_step_state(workflow, 'motion_reference', 'complete')
        workflow['current_step'] = 'final_video_generation'
        self._save_workflow(workflow)
        self.refresh_context(select_step_id='final_video_generation')
        self.status_message.emit('Video intermedio promosso a riferimento movimento; pronto per la generazione finale.')
