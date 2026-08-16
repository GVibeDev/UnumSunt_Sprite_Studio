from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from app.calibration import (
    CALIBRATION_VERDICTS,
    VARIANT_FIELDS,
    build_manual_run,
    build_single_parameter_variant,
    compare_generation_profiles,
    normalize_calibration_run,
    normalize_calibration_state,
    parse_variant_value,
    run_summary,
    sync_jobs_to_runs,
)
from app.production_presets import ProductionPresetStore, build_production_preset
from app.profile_store import ProfilesStore
from app.project_store import ProjectStore


class CalibrationWorkspace(QWidget):
    status_message = Signal(str)
    load_generation_profile_requested = Signal(dict)

    def __init__(
        self,
        *,
        project_store_provider: Callable[[], ProjectStore | None],
        active_group_id_provider: Callable[[], str | None],
        current_generation_profile_provider: Callable[[], dict[str, Any]],
    ) -> None:
        super().__init__()
        self._project_store_provider = project_store_provider
        self._active_group_id_provider = active_group_id_provider
        self._current_generation_profile_provider = current_generation_profile_provider
        self.profile_store = ProfilesStore()
        self.preset_store = ProductionPresetStore(self.profile_store)
        self._state = normalize_calibration_state(None)
        self._build_ui()
        self.refresh_context(auto_sync=True)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self.context_label = QLabel('Calibration Lab · nessun Project Group attivo')
        self.context_label.setWordWrap(True)
        self.context_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 8px; background: #24313a; border: 1px solid #536b78; }')
        root.addWidget(self.context_label)

        actions = QHBoxLayout()
        sync_button = QPushButton('Sincronizza job del gruppo')
        sync_button.clicked.connect(self._sync_jobs)
        capture_button = QPushButton('Cattura configurazione corrente')
        capture_button.clicked.connect(self._capture_current_configuration)
        load_button = QPushButton('Carica run in Genera')
        load_button.clicked.connect(self._load_selected_in_generate)
        output_button = QPushButton('Apri output')
        output_button.clicked.connect(self._open_selected_output)
        actions.addWidget(sync_button)
        actions.addWidget(capture_button)
        actions.addWidget(load_button)
        actions.addWidget(output_button)
        actions.addStretch(1)
        root.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.run_table = QTableWidget(0, 9)
        self.run_table.setHorizontalHeaderLabels([
            'Run / Job', 'Stato', 'Seed', 'Risoluzione', 'Frame', 'Steps', 'Tempo', 'Rating', 'Frame utili'
        ])
        self.run_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.run_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.run_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.run_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.run_table.horizontalHeader().setStretchLastSection(True)
        left_layout.addWidget(self.run_table, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        detail_group = QGroupBox('Run selezionato')
        detail_form = QFormLayout(detail_group)
        self.summary_label = QLabel('—')
        self.summary_label.setWordWrap(True)
        self.baseline_label = QLabel('—')
        self.environment_label = QLabel('—')
        self.environment_label.setWordWrap(True)
        detail_form.addRow('Riepilogo', self.summary_label)
        detail_form.addRow('Baseline A/B', self.baseline_label)
        detail_form.addRow('Ambiente', self.environment_label)
        right_layout.addWidget(detail_group)

        evaluation_group = QGroupBox('Valutazione produzione')
        evaluation_form = QFormLayout(evaluation_group)
        self.rating_spin = QSpinBox(); self.rating_spin.setRange(0, 5)
        self.usable_frames_spin = QSpinBox(); self.usable_frames_spin.setRange(0, 10000)
        self.verdict_combo = QComboBox()
        self.verdict_combo.addItem('Non valutato', 'unrated')
        self.verdict_combo.addItem('Da scartare', 'reject')
        self.verdict_combo.addItem('Utilizzabile', 'usable')
        self.verdict_combo.addItem('Preferito / candidato', 'preferred')
        self.notes_edit = QPlainTextEdit(); self.notes_edit.setFixedHeight(100)
        save_eval_button = QPushButton('Salva valutazione')
        save_eval_button.clicked.connect(self._save_evaluation)
        baseline_button = QPushButton('Imposta come baseline A/B')
        baseline_button.clicked.connect(self._set_baseline)
        evaluation_form.addRow('Rating 0–5', self.rating_spin)
        evaluation_form.addRow('Frame utilizzabili', self.usable_frames_spin)
        evaluation_form.addRow('Verdetto', self.verdict_combo)
        evaluation_form.addRow('Note', self.notes_edit)
        evaluation_form.addRow('', save_eval_button)
        evaluation_form.addRow('', baseline_button)
        right_layout.addWidget(evaluation_group)

        variant_group = QGroupBox('Clone / varia un solo parametro')
        variant_form = QFormLayout(variant_group)
        self.variant_field_combo = QComboBox()
        for field in VARIANT_FIELDS:
            self.variant_field_combo.addItem(field, field)
        self.variant_value_edit = QLineEdit()
        self.variant_value_edit.setPlaceholderText('Nuovo valore')
        variant_button = QPushButton('Crea variante e carica in Genera')
        variant_button.clicked.connect(self._create_variant)
        compare_button = QPushButton('Confronta 2 run selezionati')
        compare_button.clicked.connect(self._compare_selected)
        variant_form.addRow('Parametro', self.variant_field_combo)
        variant_form.addRow('Nuovo valore', self.variant_value_edit)
        variant_form.addRow('', variant_button)
        variant_form.addRow('', compare_button)
        right_layout.addWidget(variant_group)

        promote_group = QGroupBox('Promozione')
        promote_form = QFormLayout(promote_group)
        promote_generation = QPushButton('Promuovi a profilo generazione')
        promote_generation.clicked.connect(self._promote_generation_profile)
        promote_preset = QPushButton('Promuovi a preset produttivo')
        promote_preset.clicked.connect(self._promote_production_preset)
        self.promoted_label = QLabel('—')
        self.promoted_label.setWordWrap(True)
        promote_form.addRow('', promote_generation)
        promote_form.addRow('', promote_preset)
        promote_form.addRow('Promosso', self.promoted_label)
        right_layout.addWidget(promote_group)

        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([900, 520])
        root.addWidget(splitter, 1)

    def _store_and_group(self) -> tuple[ProjectStore | None, str | None]:
        return self._project_store_provider(), self._active_group_id_provider()

    def refresh_context(self, *, auto_sync: bool = False) -> None:
        store, group_id = self._store_and_group()
        if store is None or not group_id:
            self._state = normalize_calibration_state(None)
            self.context_label.setText('Calibration Lab · attivare prima un gruppo Direzione nel Project Groups.')
            self._refresh_table()
            return
        group = store.get_group(group_id)
        if not group:
            return
        self._state = normalize_calibration_state(store.get_group_calibration(group_id))
        if auto_sync:
            self._state, added = sync_jobs_to_runs(self._state, group.get('jobs', []))
            if added:
                store.set_group_calibration(group_id, self._state)
        self.context_label.setText(
            f"Calibration Lab R5e6 · {store.group_label(group_id)} · {len(self._state['runs'])} run registrati"
        )
        self._refresh_table()

    def _persist_state(self) -> None:
        store, group_id = self._store_and_group()
        if store is None or not group_id:
            return
        store.set_group_calibration(group_id, self._state)

    def _sync_jobs(self) -> None:
        store, group_id = self._store_and_group()
        if store is None or not group_id:
            QMessageBox.information(self, 'Nessun gruppo attivo', 'Attivare una direzione prima di usare il Calibration Lab.')
            return
        group = store.get_group(group_id)
        if not group:
            return
        self._state, added = sync_jobs_to_runs(self._state, group.get('jobs', []))
        self._persist_state()
        self._refresh_table(select_run_id=added[-1] if added else None)
        self.status_message.emit(f'Calibration Lab: {len(added)} nuovi job importati.')

    def _capture_current_configuration(self) -> None:
        store, group_id = self._store_and_group()
        if store is None or not group_id:
            QMessageBox.information(self, 'Nessun gruppo attivo', 'Attivare una direzione prima di catturare una configurazione.')
            return
        profile = self._current_generation_profile_provider()
        run = build_manual_run(profile)
        self._state['runs'].append(run)
        self._persist_state()
        self._refresh_table(select_run_id=run['id'])
        self.status_message.emit('Configurazione corrente registrata nel Calibration Lab.')

    def _refresh_table(self, *, select_run_id: str | None = None) -> None:
        runs = self._state.get('runs', [])
        self.run_table.setRowCount(len(runs))
        baseline = self._state.get('baseline_run_id')
        for row, raw_run in enumerate(runs):
            run = normalize_calibration_run(raw_run)
            profile = run['generation_profile']
            result = run['result']
            evaluation = run['evaluation']
            run_label = run.get('source_job_id') or run['id']
            if run['id'] == baseline:
                run_label = f'★ {run_label}'
            resolution = f"{profile.get('resolution_class', '—')} {profile.get('aspect_ratio', '')}".strip()
            duration = result.get('duration_seconds')
            duration_text = f'{float(duration):.1f}s' if isinstance(duration, (int, float)) else '—'
            values = [
                run_label,
                result.get('state', '—'),
                profile.get('seed', '—'),
                resolution or '—',
                profile.get('frames', '—'),
                profile.get('steps', '—'),
                duration_text,
                f"{evaluation.get('rating', 0)}/5",
                evaluation.get('usable_frames', 0),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, run['id'])
                self.run_table.setItem(row, col, item)
        if select_run_id:
            for row in range(self.run_table.rowCount()):
                item = self.run_table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == select_run_id:
                    self.run_table.selectRow(row)
                    break
        self._on_selection_changed()

    def _selected_run_ids(self) -> list[str]:
        rows = sorted({index.row() for index in self.run_table.selectionModel().selectedRows()})
        result: list[str] = []
        for row in rows:
            item = self.run_table.item(row, 0)
            if item:
                run_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(run_id, str):
                    result.append(run_id)
        return result

    def _run_by_id(self, run_id: str) -> dict[str, Any] | None:
        for run in self._state.get('runs', []):
            if isinstance(run, dict) and str(run.get('id')) == str(run_id):
                return run
        return None

    def _selected_run(self) -> dict[str, Any] | None:
        ids = self._selected_run_ids()
        return self._run_by_id(ids[0]) if ids else None

    def _on_selection_changed(self) -> None:
        run = self._selected_run()
        if not run:
            self.summary_label.setText('—')
            self.environment_label.setText('—')
            self.baseline_label.setText(str(self._state.get('baseline_run_id') or '—'))
            self.promoted_label.setText('—')
            return
        normalized = normalize_calibration_run(run)
        self.summary_label.setText(run_summary(normalized))
        self.baseline_label.setText('Sì' if normalized['id'] == self._state.get('baseline_run_id') else 'No')
        env = normalized.get('environment', {})
        gpus = env.get('nvidia_gpus') if isinstance(env.get('nvidia_gpus'), list) else []
        gpu_text = '; '.join(f"{gpu.get('name')} · {gpu.get('memory_total_mb')} MB · driver {gpu.get('driver_version')}" for gpu in gpus) if gpus else 'GPU non rilevata nel probe'
        self.environment_label.setText(f"{env.get('os', '—')} · {env.get('machine', '—')}\n{gpu_text}")
        evaluation = normalized['evaluation']
        self.rating_spin.setValue(int(evaluation.get('rating', 0)))
        self.usable_frames_spin.setValue(int(evaluation.get('usable_frames', 0)))
        idx = self.verdict_combo.findData(evaluation.get('verdict', 'unrated'))
        self.verdict_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.notes_edit.setPlainText(str(evaluation.get('notes', '')))
        promoted = []
        if normalized.get('promoted_generation_profile'):
            promoted.append(f"profilo: {normalized['promoted_generation_profile']}")
        if normalized.get('promoted_production_preset'):
            promoted.append(f"preset: {normalized['promoted_production_preset']}")
        self.promoted_label.setText(' · '.join(promoted) or '—')

    def _replace_run(self, run_payload: dict[str, Any]) -> None:
        run_id = str(run_payload['id'])
        for index, run in enumerate(self._state['runs']):
            if str(run.get('id')) == run_id:
                self._state['runs'][index] = normalize_calibration_run(run_payload)
                self._persist_state()
                self._refresh_table(select_run_id=run_id)
                return

    def _save_evaluation(self) -> None:
        run = self._selected_run()
        if not run:
            return
        updated = normalize_calibration_run(run)
        updated['evaluation'] = {
            'rating': self.rating_spin.value(),
            'usable_frames': self.usable_frames_spin.value(),
            'verdict': str(self.verdict_combo.currentData()),
            'notes': self.notes_edit.toPlainText().strip(),
        }
        self._replace_run(updated)
        self.status_message.emit('Valutazione Calibration Lab salvata.')

    def _set_baseline(self) -> None:
        run = self._selected_run()
        if not run:
            return
        self._state['baseline_run_id'] = str(run['id'])
        self._persist_state()
        self._refresh_table(select_run_id=str(run['id']))
        self.status_message.emit('Baseline A/B aggiornata.')

    def _load_selected_in_generate(self) -> None:
        run = self._selected_run()
        if not run:
            return
        profile = normalize_calibration_run(run)['generation_profile']
        if not profile:
            return
        self.load_generation_profile_requested.emit(deepcopy(profile))
        self.status_message.emit('Configurazione del run caricata in Genera.')

    def _create_variant(self) -> None:
        run = self._selected_run()
        if not run:
            QMessageBox.information(self, 'Nessun run', 'Selezionare prima un run di base.')
            return
        field = str(self.variant_field_combo.currentData())
        try:
            value = parse_variant_value(field, self.variant_value_edit.text())
            base_profile = normalize_calibration_run(run)['generation_profile']
            variant, change = build_single_parameter_variant(base_profile, field, value)
        except Exception as exc:
            QMessageBox.warning(self, 'Variante non valida', str(exc))
            return
        variant_run = build_manual_run(variant)
        variant_run['tags'] = ['variant', f"changed:{field}", f"from:{run['id']}"]
        variant_run['result']['variant_change'] = change
        self._state['runs'].append(variant_run)
        self._persist_state()
        self._refresh_table(select_run_id=variant_run['id'])
        self.load_generation_profile_requested.emit(deepcopy(variant))
        self.status_message.emit(f'Variante creata: solo {field} modificato; configurazione caricata in Genera.')

    def _compare_selected(self) -> None:
        ids = self._selected_run_ids()
        if len(ids) != 2:
            QMessageBox.information(self, 'Confronto A/B', 'Selezionare esattamente due run nella tabella.')
            return
        left = normalize_calibration_run(self._run_by_id(ids[0]) or {})
        right = normalize_calibration_run(self._run_by_id(ids[1]) or {})
        diffs = compare_generation_profiles(left['generation_profile'], right['generation_profile'])
        lines = [f"A: {left.get('source_job_id') or left['id']}", f"B: {right.get('source_job_id') or right['id']}", '']
        if diffs:
            lines.append('Parametri differenti:')
            for key, values in diffs.items():
                lines.append(f"• {key}: {values['left']} → {values['right']}")
        else:
            lines.append('Configurazioni generative identiche.')
        lines += ['', 'Valutazioni:', f"A: {left['evaluation']['rating']}/5 · {left['evaluation']['usable_frames']} frame utili · {left['evaluation']['verdict']}", f"B: {right['evaluation']['rating']}/5 · {right['evaluation']['usable_frames']} frame utili · {right['evaluation']['verdict']}"]
        QMessageBox.information(self, 'Confronto Calibration Lab', '\n'.join(lines))

    def _open_selected_output(self) -> None:
        run = self._selected_run()
        if not run:
            return
        result = normalize_calibration_run(run)['result']
        video_path = result.get('video_path')
        job_dir = result.get('job_directory')
        target = Path(str(video_path)) if video_path else (Path(str(job_dir)) if job_dir else None)
        if target and target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        else:
            QMessageBox.information(self, 'Output non disponibile', 'Questo run non ha un output locale disponibile.')

    def _ask_promotion_name(self, title: str, default: str) -> str | None:
        value, ok = QInputDialog.getText(self, title, 'Nome:', text=default)
        if not ok or not value.strip():
            return None
        return value.strip()

    def _promote_generation_profile(self) -> None:
        run = self._selected_run()
        if not run:
            return
        normalized = normalize_calibration_run(run)
        default = f"Calibrated · {normalized.get('source_job_id') or normalized['id']}"
        name = self._ask_promotion_name('Promuovi a profilo generazione', default)
        if not name:
            return
        self.profile_store.set_profile('generation', name, normalized['generation_profile'])
        normalized['promoted_generation_profile'] = name
        self._replace_run(normalized)
        self.status_message.emit(f'Run promosso a profilo generazione: {name}')

    def _promote_production_preset(self) -> None:
        run = self._selected_run()
        if not run:
            return
        normalized = normalize_calibration_run(run)
        default = f"Calibrated · {normalized.get('source_job_id') or normalized['id']}"
        name = self._ask_promotion_name('Promuovi a preset produttivo', default)
        if not name:
            return
        pipeline = {'generation': {'generation_profile': normalized['generation_profile']}}
        preset = build_production_preset(
            name=name,
            description=f"Promosso dal Calibration Lab R5e6. Rating {normalized['evaluation']['rating']}/5; verdict {normalized['evaluation']['verdict']}.",
            pipeline_state=pipeline,
            sections=['generation'],
            builtin=False,
            calibration_required=False,
            tags=['calibrated', 'generation', normalized['evaluation']['verdict']],
        )
        self.preset_store.save(name, preset)
        normalized['promoted_production_preset'] = name
        self._replace_run(normalized)
        self.status_message.emit(f'Run promosso a preset produttivo: {name}')
