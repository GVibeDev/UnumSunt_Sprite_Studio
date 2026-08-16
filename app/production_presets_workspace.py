from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.production_presets import (
    PRESET_SECTIONS,
    ProductionPresetStore,
    build_production_preset,
)


SECTION_LABELS = {
    'generation': 'Generazione',
    'chroma': 'Chroma / Alpha',
    'selection': 'Selezione intelligente',
    'alignment': 'Allineamento / Output Geometry',
    'export': 'Export Studio',
}


class ProductionPresetsWorkspace(QWidget):
    status_message = Signal(str)

    def __init__(
        self,
        *,
        active_group_provider: Callable[[], dict | None],
        pipeline_provider: Callable[[], dict],
        apply_callback: Callable[[str, dict, list[str]], None],
    ) -> None:
        super().__init__()
        self._active_group_provider = active_group_provider
        self._pipeline_provider = pipeline_provider
        self._apply_callback = apply_callback
        self.store = ProductionPresetStore()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        banner = QLabel(
            'R5e4a Preset Produttivi — cattura configurazioni riutilizzabili della pipeline e applicale ai Project Groups. '
            'I preset Starter non impongono parametri WAN non calibrati.'
        )
        banner.setWordWrap(True)
        banner.setStyleSheet('QLabel { color: #f4f6f8; padding: 9px; background: #332d1f; border: 1px solid #8c7b43; }')
        root.addWidget(banner)

        self.active_group_label = QLabel('Gruppo attivo: nessuno')
        self.active_group_label.setWordWrap(True)
        self.active_group_label.setStyleSheet('QLabel { padding: 7px; border: 1px solid #555; }')
        root.addWidget(self.active_group_label)

        splitter = QSplitter()
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 5, 0)
        self.preset_list = QListWidget()
        self.preset_list.currentTextChanged.connect(self._on_selected_preset_changed)
        left_layout.addWidget(self.preset_list, 1)
        list_actions = QHBoxLayout()
        refresh_button = QPushButton('Aggiorna')
        refresh_button.clicked.connect(self.refresh)
        duplicate_button = QPushButton('Duplica')
        duplicate_button.clicked.connect(self._duplicate_selected)
        delete_button = QPushButton('Elimina')
        delete_button.clicked.connect(self._delete_selected)
        list_actions.addWidget(refresh_button)
        list_actions.addWidget(duplicate_button)
        list_actions.addWidget(delete_button)
        left_layout.addLayout(list_actions)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(5, 0, 0, 0)

        details_group = QGroupBox('Preset selezionato')
        details_form = QFormLayout(details_group)
        self.preset_name_label = QLabel('—')
        self.preset_type_label = QLabel('—')
        self.calibration_label = QLabel('—')
        self.description_edit = QPlainTextEdit()
        self.description_edit.setReadOnly(True)
        self.description_edit.setMaximumHeight(110)
        self.tags_label = QLabel('—')
        self.tags_label.setWordWrap(True)
        details_form.addRow('Nome', self.preset_name_label)
        details_form.addRow('Tipo', self.preset_type_label)
        details_form.addRow('Calibrazione WAN', self.calibration_label)
        details_form.addRow('Descrizione', self.description_edit)
        details_form.addRow('Tag', self.tags_label)
        right_layout.addWidget(details_group)

        sections_group = QGroupBox('Sezioni da catturare / applicare')
        sections_layout = QVBoxLayout(sections_group)
        self.section_checks: dict[str, QCheckBox] = {}
        for key in PRESET_SECTIONS:
            check = QCheckBox(SECTION_LABELS[key])
            check.setChecked(True)
            self.section_checks[key] = check
            sections_layout.addWidget(check)
        right_layout.addWidget(sections_group)

        actions_group = QGroupBox('Azioni')
        actions_layout = QVBoxLayout(actions_group)
        capture_button = QPushButton('Cattura pipeline corrente come nuovo preset')
        capture_button.clicked.connect(self._capture_current)
        apply_button = QPushButton('Applica preset al gruppo attivo')
        apply_button.clicked.connect(self._apply_selected)
        actions_layout.addWidget(capture_button)
        actions_layout.addWidget(apply_button)
        right_layout.addWidget(actions_group)

        note = QLabel(
            'La cattura salva solo impostazioni riutilizzabili: non include file sorgente, video, frame selezionati, '
            'override manuali del clean-up o stati per-frame dell’allineamento. Durante l’applicazione questi dati del gruppo vengono preservati.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color: #aaa;')
        right_layout.addWidget(note)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

    def selected_sections(self) -> list[str]:
        return [key for key, check in self.section_checks.items() if check.isChecked()]

    def _current_name(self) -> str:
        item = self.preset_list.currentItem()
        return item.text().strip() if item else ''

    def refresh_context(self) -> None:
        group = self._active_group_provider()
        if not group:
            self.active_group_label.setText('Gruppo attivo: nessuno')
            return
        assigned = group.get('metadata', {}).get('production_preset') if isinstance(group.get('metadata'), dict) else None
        suffix = ''
        if isinstance(assigned, dict) and assigned.get('name'):
            suffix = f" · preset assegnato: {assigned['name']}"
        self.active_group_label.setText(f"Gruppo attivo: {group.get('label', group.get('name', '—'))}{suffix}")

    def refresh(self, select_name: str | None = None) -> None:
        self.store.ensure_starters()
        names = self.store.list_names()
        current = select_name or self._current_name()
        self.preset_list.clear()
        self.preset_list.addItems(names)
        if current in names:
            # PySide6 requires Qt.MatchFlag for QListWidget.findItems(); passing
            # the legacy integer 0 raises TypeError on current bindings. Since
            # `names` is the exact source used to populate the list, selecting
            # by row is simpler, exact and binding-independent.
            self.preset_list.setCurrentRow(names.index(current))
        elif names:
            self.preset_list.setCurrentRow(0)
        self.refresh_context()

    def _on_selected_preset_changed(self, name: str) -> None:
        preset = self.store.get(name)
        if not preset:
            self.preset_name_label.setText('—')
            self.preset_type_label.setText('—')
            self.calibration_label.setText('—')
            self.description_edit.clear()
            self.tags_label.setText('—')
            return
        self.preset_name_label.setText(str(preset.get('name', name)))
        self.preset_type_label.setText('Starter integrato' if preset.get('builtin') else 'Personalizzato')
        if preset.get('calibration_required'):
            self.calibration_label.setText('Da calibrare / completare')
        else:
            self.calibration_label.setText('Catturato dall’utente')
        self.description_edit.setPlainText(str(preset.get('description', '')))
        self.tags_label.setText(', '.join(str(tag) for tag in preset.get('tags', [])) or '—')
        available = set(preset.get('sections', []))
        for key, check in self.section_checks.items():
            check.setChecked(key in available)

    def _capture_current(self) -> None:
        group = self._active_group_provider()
        if not group:
            QMessageBox.information(self, 'Nessun gruppo attivo', 'Attivare prima una direzione nel Project Groups.')
            return
        sections = self.selected_sections()
        if not sections:
            QMessageBox.information(self, 'Nessuna sezione', 'Selezionare almeno una sezione da catturare.')
            return
        name, ok = QInputDialog.getText(self, 'Nuovo preset produttivo', 'Nome preset:')
        if not ok or not name.strip():
            return
        description, ok = QInputDialog.getMultiLineText(
            self,
            'Descrizione preset',
            'Descrizione / uso previsto:',
            f"Catturato da {group.get('label', group.get('name', 'gruppo attivo'))}",
        )
        if not ok:
            return
        pipeline = self._pipeline_provider()
        preset = build_production_preset(
            name=name.strip(),
            description=description,
            pipeline_state=pipeline,
            sections=sections,
            builtin=False,
            calibration_required=False,
            tags=['custom', 'captured'],
        )
        if not preset.get('sections'):
            QMessageBox.warning(self, 'Preset vuoto', 'Le sezioni selezionate non contengono impostazioni riutilizzabili.')
            return
        self.store.save(name.strip(), preset)
        self.refresh(select_name=name.strip())
        self.status_message.emit(f'Preset produttivo salvato: {name.strip()}')

    def _apply_selected(self) -> None:
        name = self._current_name()
        preset = self.store.get(name) if name else None
        if not preset:
            return
        group = self._active_group_provider()
        if not group:
            QMessageBox.information(self, 'Nessun gruppo attivo', 'Attivare prima una direzione nel Project Groups.')
            return
        available = set(preset.get('sections', []))
        sections = [section for section in self.selected_sections() if section in available]
        if not sections:
            QMessageBox.information(self, 'Nessuna sezione', 'Il preset non contiene nessuna delle sezioni selezionate.')
            return
        if preset.get('calibration_required'):
            answer = QMessageBox.question(
                self,
                'Preset Starter',
                'Questo è un preset strutturale Starter: non contiene parametri WAN calibrati. Applicare comunque le sezioni disponibili?',
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._apply_callback(name, preset, sections)
        self.refresh_context()
        self.status_message.emit(f'Preset applicato al gruppo attivo: {name}')

    def _duplicate_selected(self) -> None:
        source = self._current_name()
        if not source:
            return
        target, ok = QInputDialog.getText(self, 'Duplica preset', 'Nome della copia:', text=f'{source} copy')
        if not ok or not target.strip():
            return
        try:
            self.store.duplicate(source, target.strip())
        except Exception as exc:
            QMessageBox.critical(self, 'Errore duplicazione', str(exc))
            return
        self.refresh(select_name=target.strip())
        self.status_message.emit(f'Preset duplicato: {target.strip()}')

    def _delete_selected(self) -> None:
        name = self._current_name()
        if not name:
            return
        preset = self.store.get(name)
        if preset and preset.get('builtin'):
            QMessageBox.information(self, 'Preset Starter', 'I preset Starter integrati non possono essere eliminati. Duplicarli per creare una variante personalizzata.')
            return
        answer = QMessageBox.question(self, 'Elimina preset', f'Eliminare il preset "{name}"?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete(name)
        except Exception as exc:
            QMessageBox.critical(self, 'Errore eliminazione', str(exc))
            return
        self.refresh()
        self.status_message.emit(f'Preset eliminato: {name}')
