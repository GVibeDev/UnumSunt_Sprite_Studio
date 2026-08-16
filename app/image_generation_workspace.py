from __future__ import annotations

from datetime import datetime
from pathlib import Path
import uuid

from PySide6.QtCore import QTimer, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.generation.image_provider import (
    LocalWanGPImageConfig,
    LocalWanGPImageProvider,
    MockImageProvider,
)
from app.generation.local_wangp import LocalWanGPConfig
from app.generation.manager import GenerationJobManager
from app.generation.models import GenerationRequest
from app.generation.registry import ProviderRegistry


class ImageGenerationWorkspace(QWidget):
    image_ready = Signal(str)
    job_started = Signal(str)
    job_finished = Signal(dict)
    status_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.local_config = LocalWanGPImageConfig.load()
        self.local_provider = LocalWanGPImageProvider(self.local_config)
        self.registry = ProviderRegistry([MockImageProvider(), self.local_provider])
        self.manager = GenerationJobManager(self.registry)
        self.current_job_id: str | None = None
        self.last_image_path: str | None = None
        self.last_manifest_path: str | None = None
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(150)
        self.poll_timer.timeout.connect(self._poll_job)
        self._build_ui()
        self._load_config()
        self._refresh_provider()
        self._default_state = self.snapshot_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        banner = QLabel(
            'R5e9 — Local Image Generation Provider. Il core resta indipendente dal runtime AI: '
            'la generazione immagine usa provider separati e produce PNG + manifest normalizzati.'
        )
        banner.setWordWrap(True)
        banner.setStyleSheet('QLabel { color: #f4f6f8; padding: 9px; background: #253246; border: 1px solid #486b96; }')
        root.addWidget(banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)

        provider_group = QGroupBox('Provider immagine')
        provider_form = QFormLayout(provider_group)
        self.provider_combo = QComboBox()
        for provider in self.registry.list():
            self.provider_combo.addItem(provider.display_name, provider.provider_id)
        self.provider_combo.currentIndexChanged.connect(self._refresh_provider)
        self.task_combo = QComboBox()
        self.task_combo.addItem('Text → Image', 'text_to_image')
        self.task_combo.addItem('Image → Image', 'image_to_image')
        self.task_combo.currentIndexChanged.connect(self._refresh_task)
        self.model_edit = QLineEdit('wan_image_local')
        self.capabilities_label = QLabel('—')
        self.capabilities_label.setWordWrap(True)
        provider_form.addRow('Provider', self.provider_combo)
        provider_form.addRow('Task', self.task_combo)
        provider_form.addRow('Model label', self.model_edit)
        provider_form.addRow('Capacità', self.capabilities_label)
        left_layout.addWidget(provider_group)

        input_group = QGroupBox('Master e prompt')
        input_form = QFormLayout(input_group)
        self.reference_edit, reference_row = self._path_row(self._choose_reference)
        self.positive_prompt = QPlainTextEdit('full body character concept, clean silhouette, fixed neutral composition')
        self.positive_prompt.setFixedHeight(90)
        self.negative_prompt = QPlainTextEdit('cropped body, duplicate limbs, text, watermark, cluttered background')
        self.negative_prompt.setFixedHeight(70)
        input_form.addRow('Master image (I2I)', reference_row)
        input_form.addRow('Prompt', self.positive_prompt)
        input_form.addRow('Negative', self.negative_prompt)
        left_layout.addWidget(input_group)

        generation_group = QGroupBox('Parametri immagine')
        generation_form = QFormLayout(generation_group)
        self.seed_spin = QSpinBox(); self.seed_spin.setRange(0, 2_147_483_647); self.seed_spin.setValue(18274)
        self.width_spin = QSpinBox(); self.width_spin.setRange(64, 4096); self.width_spin.setSingleStep(64); self.width_spin.setValue(1024)
        self.height_spin = QSpinBox(); self.height_spin.setRange(64, 4096); self.height_spin.setSingleStep(64); self.height_spin.setValue(1024)
        self.steps_spin = QSpinBox(); self.steps_spin.setRange(1, 200); self.steps_spin.setValue(30)
        generation_form.addRow('Seed', self.seed_spin)
        generation_form.addRow('Width', self.width_spin)
        generation_form.addRow('Height', self.height_spin)
        generation_form.addRow('Steps', self.steps_spin)
        left_layout.addWidget(generation_group)

        self.runtime_group = QGroupBox('WanGP Image Runtime')
        runtime_form = QFormLayout(self.runtime_group)
        self.python_edit, python_row = self._path_row(self._choose_python)
        self.wangp_edit, wangp_row = self._path_row(self._choose_wangp)
        self.template_edit, template_row = self._path_row(self._choose_template)
        self.working_dir_edit, working_row = self._path_row(self._choose_working_dir, directory=True)

        self.memory_profile_combo = QComboBox()
        self.memory_profile_combo.addItem('Auto / default WanGP', '')
        self.memory_profile_combo.addItem('1 — HighRAM / HighVRAM', '1')
        self.memory_profile_combo.addItem('2 — HighRAM / LowVRAM', '2')
        self.memory_profile_combo.addItem('3 — LowRAM / HighVRAM', '3')
        self.memory_profile_combo.addItem('4 — LowRAM / LowVRAM', '4')
        self.memory_profile_combo.addItem('5 — VeryLowRAM / LowVRAM', '5')
        self.memory_profile_combo.setToolTip(
            'Profilo memoria/offloading passato a WanGP come --profile. '
            'In caso di CUDA OOM prova prima il profilo 5, poi il 4.'
        )

        self.reserved_ram_spin = QDoubleSpinBox()
        self.reserved_ram_spin.setRange(0.0, 1.0)
        self.reserved_ram_spin.setDecimals(2)
        self.reserved_ram_spin.setSingleStep(0.05)
        self.reserved_ram_spin.setValue(0.0)
        self.reserved_ram_spin.setSpecialValueText('Auto')
        self.reserved_ram_spin.setToolTip(
            'Valore opzionale per --perc-reserved-mem-max. 0.00 = non forzare. '
            'Per un test conservativo usare 0.20.'
        )

        actions = QWidget()
        actions_layout = QHBoxLayout(actions); actions_layout.setContentsMargins(0, 0, 0, 0)
        save_button = QPushButton('Salva runtime'); save_button.clicked.connect(self._save_config)
        health_button = QPushButton('Health check'); health_button.clicked.connect(self._health_check)
        inherit_button = QPushButton('Eredita runtime video'); inherit_button.clicked.connect(self._inherit_video_runtime)
        actions_layout.addWidget(save_button); actions_layout.addWidget(health_button); actions_layout.addWidget(inherit_button)
        self.health_report = QPlainTextEdit(); self.health_report.setReadOnly(True); self.health_report.setMaximumHeight(130)
        runtime_form.addRow('Python 3.11', python_row)
        runtime_form.addRow('WanGP wgp.py', wangp_row)
        runtime_form.addRow('Image settings JSON', template_row)
        runtime_form.addRow('WanGP root', working_row)
        runtime_form.addRow('Memory profile', self.memory_profile_combo)
        runtime_form.addRow('Reserved RAM max', self.reserved_ram_spin)
        runtime_form.addRow('', actions)
        runtime_form.addRow('Report', self.health_report)
        left_layout.addWidget(self.runtime_group)

        generate_row = QHBoxLayout()
        self.validate_button = QPushButton('Valida')
        self.validate_button.clicked.connect(self._validate)
        self.generate_button = QPushButton('Genera immagine')
        self.generate_button.clicked.connect(self._generate)
        self.cancel_button = QPushButton('Annulla')
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(False)
        generate_row.addWidget(self.validate_button)
        generate_row.addWidget(self.generate_button)
        generate_row.addWidget(self.cancel_button)
        left_layout.addLayout(generate_row)
        left_layout.addStretch(1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 0, 0, 0)
        status_group = QGroupBox('Job immagine')
        status_form = QFormLayout(status_group)
        self.job_label = QLabel('—')
        self.state_label = QLabel('idle')
        self.message_label = QLabel('Nessun job avviato'); self.message_label.setWordWrap(True)
        self.progress = QProgressBar(); self.progress.setRange(0, 1000)
        status_form.addRow('Job', self.job_label)
        status_form.addRow('Stato', self.state_label)
        status_form.addRow('Dettaglio', self.message_label)
        status_form.addRow('Progresso', self.progress)
        right_layout.addWidget(status_group)

        preview_group = QGroupBox('Output normalizzato')
        preview_layout = QVBoxLayout(preview_group)
        self.preview = QLabel('Nessuna immagine generata')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(420, 420)
        self.preview.setStyleSheet('QLabel { color: #f4f6f8; background: #17191d; border: 1px solid #444; }')
        self.output_label = QLabel('—'); self.output_label.setWordWrap(True)
        output_actions = QHBoxLayout()
        self.use_reference_button = QPushButton('Usa come reference WAN')
        self.use_reference_button.clicked.connect(self._emit_image_ready)
        self.use_reference_button.setEnabled(False)
        self.open_folder_button = QPushButton('Apri cartella job')
        self.open_folder_button.clicked.connect(self._open_folder)
        self.open_folder_button.setEnabled(False)
        output_actions.addWidget(self.use_reference_button)
        output_actions.addWidget(self.open_folder_button)
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addWidget(self.output_label)
        preview_layout.addLayout(output_actions)
        right_layout.addWidget(preview_group, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)
        self._refresh_task()

    @staticmethod
    def _path_row(callback, *, directory: bool = False) -> tuple[QLineEdit, QWidget]:
        edit = QLineEdit()
        button = QPushButton('…')
        button.setFixedWidth(36)
        button.clicked.connect(callback)
        row = QWidget()
        layout = QHBoxLayout(row); layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit, 1); layout.addWidget(button)
        return edit, row

    def _choose_reference(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Seleziona master image', '', 'Immagini (*.png *.webp *.jpg *.jpeg);;Tutti i file (*)')
        if path:
            self.reference_edit.setText(path)

    def _choose_python(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Python WanGP', '', 'Eseguibili (*.exe);;Tutti i file (*)')
        if path:
            self.python_edit.setText(path)

    def _choose_wangp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'WanGP wgp.py', '', 'Python (*.py);;Tutti i file (*)')
        if path:
            self.wangp_edit.setText(path)

    def _choose_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Preset/settings immagine WanGP', '', 'JSON (*.json);;Tutti i file (*)')
        if path:
            self.template_edit.setText(path)

    def _choose_working_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, 'WanGP root')
        if path:
            self.working_dir_edit.setText(path)

    def _refresh_provider(self, *_args) -> None:
        provider = self.registry.get(str(self.provider_combo.currentData()))
        caps = provider.get_capabilities()
        self.capabilities_label.setText(
            f"T2I {'✓' if caps.text_to_image else '—'} · I2I {'✓' if caps.image_to_image else '—'} · "
            f"seed {'✓' if caps.fixed_seed else '—'} · cancel {'✓' if caps.cancellation else '—'}"
        )
        self.runtime_group.setVisible(provider.provider_id == 'local_wangp_image')

    def _refresh_task(self, *_args) -> None:
        self.reference_edit.setEnabled(str(self.task_combo.currentData()) == 'image_to_image')

    def _config_from_ui(self) -> LocalWanGPImageConfig:
        return LocalWanGPImageConfig(
            python_executable=self.python_edit.text().strip(),
            wangp_script=self.wangp_edit.text().strip(),
            settings_template=self.template_edit.text().strip(),
            working_directory=self.working_dir_edit.text().strip(),
            verbose=self.local_config.verbose,
            strict_python_311=self.local_config.strict_python_311,
            require_template=True,
            process_timeout_seconds=self.local_config.process_timeout_seconds,
            extra_arguments=list(self.local_config.extra_arguments),
            memory_profile=str(self.memory_profile_combo.currentData() or '').strip(),
            reserved_memory_max=float(self.reserved_ram_spin.value()),
        )

    def _load_config(self) -> None:
        self.python_edit.setText(self.local_config.python_executable)
        self.wangp_edit.setText(self.local_config.wangp_script)
        self.template_edit.setText(self.local_config.settings_template)
        self.working_dir_edit.setText(self.local_config.working_directory)
        index = self.memory_profile_combo.findData(str(self.local_config.memory_profile or ''))
        self.memory_profile_combo.setCurrentIndex(index if index >= 0 else 0)
        self.reserved_ram_spin.setValue(float(self.local_config.reserved_memory_max or 0.0))

    def reload_local_runtime_config(self) -> None:
        self.local_config = LocalWanGPImageConfig.load()
        self.local_provider.update_config(self.local_config)
        self._load_config()
        self.status_message.emit('Configurazione runtime WanGP Image ricaricata dal Runtime Manager.')

    def _save_config(self) -> None:
        self.local_config = self._config_from_ui()
        self.local_config.save()
        self.local_provider.update_config(self.local_config)
        self.status_message.emit('Configurazione WanGP Image salvata.')

    def _inherit_video_runtime(self) -> None:
        inherited = LocalWanGPImageConfig.from_video_config(LocalWanGPConfig.load())
        # Never overwrite Image Gen-specific settings while inheriting runtime paths.
        inherited.settings_template = self.template_edit.text().strip()
        inherited.memory_profile = str(self.memory_profile_combo.currentData() or '').strip()
        inherited.reserved_memory_max = float(self.reserved_ram_spin.value())
        self.local_config = inherited
        self._load_config()
        self.local_provider.update_config(inherited)
        self.status_message.emit('Runtime Python/WanGP ereditato dalla configurazione video.')

    def _health_check(self) -> None:
        self.local_config = self._config_from_ui()
        self.local_provider.update_config(self.local_config)
        report = self.local_provider.health_check().summary()
        profile = self.local_config.memory_profile or 'Auto'
        reserved = (
            f'{self.local_config.reserved_memory_max:.2f}'
            if self.local_config.reserved_memory_max > 0
            else 'Auto'
        )
        self.health_report.setPlainText(
            report + f'\nImage memory profile: {profile} · Reserved RAM max: {reserved}'
        )

    def _request(self) -> GenerationRequest:
        return GenerationRequest(
            job_id=f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
            provider=str(self.provider_combo.currentData()),
            model=self.model_edit.text().strip() or 'wan_image_local',
            task=str(self.task_combo.currentData()),
            reference_image=(self.reference_edit.text().strip() or None) if str(self.task_combo.currentData()) == 'image_to_image' else None,
            motion_video=None,
            positive_prompt=self.positive_prompt.toPlainText().strip(),
            negative_prompt=self.negative_prompt.toPlainText().strip(),
            seed=int(self.seed_spin.value()),
            width=int(self.width_spin.value()),
            height=int(self.height_spin.value()),
            frames=1,
            fps=1.0,
            steps=int(self.steps_spin.value()),
            metadata={'media_kind': 'image', 'r5e9': True},
        )

    def _validate(self) -> None:
        if str(self.provider_combo.currentData()) == 'local_wangp_image':
            self.local_config = self._config_from_ui()
            self.local_provider.update_config(self.local_config)
        try:
            request = self._request()
            self.registry.get(request.provider).validate_request(request)
        except Exception as exc:
            QMessageBox.warning(self, 'Validazione immagine', str(exc))
            return
        self.status_message.emit('R5e9: richiesta immagine valida.')

    def _generate(self) -> None:
        if self.current_job_id:
            return
        if str(self.provider_combo.currentData()) == 'local_wangp_image':
            self.local_config = self._config_from_ui()
            self.local_provider.update_config(self.local_config)
        try:
            request = self._request()
            job_id = self.manager.submit(request)
        except Exception as exc:
            QMessageBox.critical(self, 'Generazione immagine', str(exc))
            return
        self.current_job_id = job_id
        self.job_label.setText(job_id)
        self.state_label.setText('queued')
        self.message_label.setText('Job immagine in coda')
        self.progress.setValue(0)
        self.generate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.job_started.emit(job_id)
        self.poll_timer.start()

    def _poll_job(self) -> None:
        if not self.current_job_id:
            self.poll_timer.stop()
            return
        snapshot = self.manager.get_snapshot(self.current_job_id)
        if snapshot is None:
            return
        self.state_label.setText(snapshot.state)
        self.message_label.setText(snapshot.message)
        self.progress.setValue(int(max(0.0, min(1.0, snapshot.progress)) * 1000))
        if snapshot.state not in {'completed', 'failed', 'cancelled'}:
            return
        self.poll_timer.stop()
        payload = snapshot.to_dict()
        self.job_finished.emit(payload)
        result = snapshot.result
        if result is not None and result.state == 'completed' and result.image_path:
            self.last_image_path = str(Path(result.image_path).resolve())
            manifest_path = Path(snapshot.job_directory) / 'image_generation_manifest.json'
            self.last_manifest_path = str(manifest_path.resolve()) if manifest_path.is_file() else None
            self.output_label.setText(self.last_image_path)
            self._show_preview(self.last_image_path)
            self.use_reference_button.setEnabled(True)
            self.open_folder_button.setEnabled(True)
            self.status_message.emit(f'Immagine generata: {Path(self.last_image_path).name}')
            # R5e9 acceptance contract: a successful local image becomes
            # immediately available as the WAN reference through the host app.
            self.image_ready.emit(self.last_image_path)
        elif result is not None and result.error_message:
            self.output_label.setText(result.error_message)
        self.current_job_id = None
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def _show_preview(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview.setText('Preview non disponibile')
            return
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _cancel(self) -> None:
        if self.current_job_id and self.manager.cancel(self.current_job_id):
            self.message_label.setText('Annullamento richiesto…')

    def _emit_image_ready(self) -> None:
        if self.last_image_path and Path(self.last_image_path).is_file():
            self.image_ready.emit(self.last_image_path)

    def _open_folder(self) -> None:
        if not self.last_image_path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.last_image_path).parent)))


    def reset_context(self) -> None:
        """Reset group-specific image-generation state without touching runtime config."""
        default = dict(getattr(self, '_default_state', {}))
        default['last_image_path'] = None
        default['reference_image'] = ''
        self.last_image_path = None
        self.last_manifest_path = None
        self.output_label.setText('—')
        self.preview.setPixmap(QPixmap())
        self.preview.setText('Nessuna immagine generata')
        self.use_reference_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.apply_state(default)

    def snapshot_state(self) -> dict:
        return {
            'provider_id': str(self.provider_combo.currentData()),
            'task': str(self.task_combo.currentData()),
            'model': self.model_edit.text().strip(),
            'reference_image': self.reference_edit.text().strip(),
            'positive_prompt': self.positive_prompt.toPlainText(),
            'negative_prompt': self.negative_prompt.toPlainText(),
            'seed': int(self.seed_spin.value()),
            'width': int(self.width_spin.value()),
            'height': int(self.height_spin.value()),
            'steps': int(self.steps_spin.value()),
            'last_image_path': self.last_image_path,
            'last_manifest_path': self.last_manifest_path,
        }

    def apply_state(self, state: dict) -> None:
        if not isinstance(state, dict):
            return
        provider_id = str(state.get('provider_id', self.provider_combo.currentData()))
        idx = self.provider_combo.findData(provider_id)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        task = str(state.get('task', self.task_combo.currentData()))
        idx = self.task_combo.findData(task)
        if idx >= 0:
            self.task_combo.setCurrentIndex(idx)
        self.model_edit.setText(str(state.get('model', self.model_edit.text())))
        self.reference_edit.setText(str(state.get('reference_image', '')))
        self.positive_prompt.setPlainText(str(state.get('positive_prompt', self.positive_prompt.toPlainText())))
        self.negative_prompt.setPlainText(str(state.get('negative_prompt', self.negative_prompt.toPlainText())))
        self.seed_spin.setValue(int(state.get('seed', self.seed_spin.value())))
        self.width_spin.setValue(int(state.get('width', self.width_spin.value())))
        self.height_spin.setValue(int(state.get('height', self.height_spin.value())))
        self.steps_spin.setValue(int(state.get('steps', self.steps_spin.value())))
        last = state.get('last_image_path')
        manifest = state.get('last_manifest_path')
        self.last_image_path = str(last) if last and Path(str(last)).is_file() else None
        self.last_manifest_path = str(manifest) if manifest and Path(str(manifest)).is_file() else None
        if self.last_image_path:
            self.output_label.setText(self.last_image_path)
            self._show_preview(self.last_image_path)
            self.use_reference_button.setEnabled(True)
            self.open_folder_button.setEnabled(True)
        self._refresh_provider()
        self._refresh_task()
