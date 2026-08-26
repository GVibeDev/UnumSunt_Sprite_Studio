from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFrame,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.generation.local_wangp import LocalWanGPConfig, LocalWanGPProvider
from app.generation.manager import GenerationJobManager
from app.generation.mock_provider import MockVideoProvider
from app.generation.models import GenerationRequest
from app.generation.registry import ProviderRegistry
from app.generation.wan_contract import (
    WanResolutionOption,
    merged_resolution_options,
    normalize_wan_frame_count,
    option_for_selection,
    read_force_fps,
    resolve_fps_contract,
    template_resolution_option,
)
from app.video_source import VideoOpenError, VideoSource
from app.profile_store import ProfilesStore


class GenerationWorkspace(QWidget):
    video_ready = Signal(str)
    job_started = Signal(str)
    job_finished = Signal(dict)
    status_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.profile_store = ProfilesStore()
        self.local_config = LocalWanGPConfig.load()
        self.local_provider = LocalWanGPProvider(self.local_config)
        self.registry = ProviderRegistry([MockVideoProvider(), self.local_provider])
        self.manager = GenerationJobManager(self.registry)
        self.current_job_id: str | None = None
        self.last_video_path: str | None = None
        self.requested_background_rgb = (0, 255, 0)
        self.prompt_profile_name = ''
        self.prompt_builder_state: dict = {}
        self._resolution_options: list[WanResolutionOption] = []
        self._motion_fps_cache: dict[str, float | None] = {}
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(120)
        self.poll_timer.timeout.connect(self._poll_current_job)
        self._build_ui()
        self._load_local_config_into_ui()
        self._reload_wan_resolution_options()
        self._refresh_provider_ui()
        self._refresh_generation_profiles_combo()
        self._load_last_used_generation_profile()
        self._update_generation_contract()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        banner = QLabel(
            'R5e12 — Consolidated generation: the WanGP contract is unchanged, panels are organized by task, and fields remain responsive to avoid compression. The 4n+1 frame rule and FPS contract are unchanged.'
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            'QLabel { color: #f4f6f8; padding: 9px; background: #20382a; border: 1px solid #3d7b55; }'
        )
        root.addWidget(banner)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        request_panel = QWidget()
        request_layout = QVBoxLayout(request_panel)
        request_layout.setContentsMargins(0, 0, 6, 0)

        profiles_group = QGroupBox('Generation Profiles')
        profiles_form = QFormLayout(profiles_group)
        self._configure_form_layout(profiles_form)
        self.generation_profile_combo = QComboBox()
        self.generation_profile_combo.setMinimumWidth(280)
        profiles_actions = QWidget()
        profiles_actions_layout = QHBoxLayout(profiles_actions)
        profiles_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.load_generation_profile_button = QPushButton('Load')
        self.load_generation_profile_button.clicked.connect(self._load_selected_generation_profile)
        self.save_generation_profile_button = QPushButton('Save Current')
        self.save_generation_profile_button.clicked.connect(self._save_current_generation_profile_as)
        self.delete_generation_profile_button = QPushButton('Delete')
        self.delete_generation_profile_button.clicked.connect(self._delete_selected_generation_profile)
        profiles_actions_layout.addWidget(self.load_generation_profile_button)
        profiles_actions_layout.addWidget(self.delete_generation_profile_button)
        profiles_actions_layout.addWidget(self.save_generation_profile_button)
        profiles_form.addRow('Profile', self.generation_profile_combo)
        profiles_form.addRow('', profiles_actions)
        self.profiles_group = profiles_group

        provider_group = QGroupBox('Provider')
        provider_form = QFormLayout(provider_group)
        self._configure_form_layout(provider_form)
        self.provider_combo = QComboBox()
        for provider in self.registry.list():
            self.provider_combo.addItem(provider.display_name, provider.provider_id)
        self.provider_combo.currentIndexChanged.connect(self._refresh_provider_ui)
        self.model_combo = QComboBox()
        self.capabilities_label = QLabel('—')
        self.capabilities_label.setWordWrap(True)
        self.privacy_label = QLabel('—')
        self.privacy_label.setWordWrap(True)
        self.privacy_label.setStyleSheet('color: #8fc9a4;')
        provider_form.addRow('Rendering engine', self.provider_combo)
        provider_form.addRow('Model', self.model_combo)
        provider_form.addRow('Capabilities', self.capabilities_label)
        provider_form.addRow('Privacy', self.privacy_label)
        self.provider_group = provider_group

        self.runtime_group = QGroupBox('Local WanGP bridge configuration')
        runtime_form = QFormLayout(self.runtime_group)
        self._configure_form_layout(runtime_form)
        self.python_edit, python_row = self._path_row(self._choose_python)
        self.wangp_edit, wangp_row = self._path_row(self._choose_wangp_script)
        self.template_edit, template_row = self._path_row(self._choose_template)
        self.working_dir_edit, working_row = self._path_row(self._choose_working_directory, directory=True)
        self.strict_python_checkbox = QCheckBox('Require Python 3.11.x')
        self.strict_python_checkbox.setChecked(True)
        self.require_template_checkbox = QCheckBox('Require WanGP JSON template')
        self.require_template_checkbox.setChecked(True)
        self.verbose_spin = QSpinBox(); self.verbose_spin.setRange(0, 5); self.verbose_spin.setValue(2)
        runtime_actions = QWidget()
        runtime_actions_layout = QHBoxLayout(runtime_actions)
        runtime_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.save_runtime_button = QPushButton('Save Configuration')
        self.save_runtime_button.clicked.connect(self._save_local_config)
        self.health_button = QPushButton('Health check')
        self.health_button.clicked.connect(self._run_health_check)
        self.dry_run_button = QPushButton('Dry-run')
        self.dry_run_button.clicked.connect(self._submit_dry_run)
        runtime_actions_layout.addWidget(self.save_runtime_button)
        runtime_actions_layout.addWidget(self.health_button)
        runtime_actions_layout.addWidget(self.dry_run_button)
        self.health_report = QPlainTextEdit()
        self.health_report.setReadOnly(True)
        self.health_report.setMaximumHeight(150)
        runtime_form.addRow('Python executable', python_row)
        runtime_form.addRow('WanGP wgp.py', wangp_row)
        runtime_form.addRow('Settings template', template_row)
        runtime_form.addRow('WanGP root (folder containing wgp.py)', working_row)
        runtime_form.addRow('Verbose', self.verbose_spin)
        runtime_form.addRow('', self.strict_python_checkbox)
        runtime_form.addRow('', self.require_template_checkbox)
        runtime_form.addRow('', runtime_actions)
        runtime_form.addRow('Report', self.health_report)

        inputs_group = QGroupBox('Input and Prompt')
        inputs_form = QFormLayout(inputs_group)
        self._configure_form_layout(inputs_form)
        self.reference_edit, reference_row = self._path_row(self._choose_reference)
        self.motion_edit, motion_row = self._path_row(self._choose_motion_reference)
        self.positive_prompt = QPlainTextEdit(
            'Character performs a clean walk cycle on a flat green background, fixed camera.'
        )
        self.positive_prompt.setFixedHeight(86)
        self.negative_prompt = QPlainTextEdit(
            'camera movement, scene cuts, changing identity, background objects'
        )
        self.negative_prompt.setFixedHeight(66)
        self.background_button = QPushButton('Choose Requested Color')
        self.background_button.clicked.connect(self._choose_requested_background)
        self.background_swatch = QFrame()
        self.background_swatch.setMinimumHeight(28)
        self.background_swatch.setFrameShape(QFrame.Shape.StyledPanel)
        background_row = QWidget()
        background_layout = QHBoxLayout(background_row)
        background_layout.setContentsMargins(0, 0, 0, 0)
        background_layout.addWidget(self.background_button)
        background_layout.addWidget(self.background_swatch, 1)
        self._update_requested_background_swatch()
        inputs_form.addRow('Reference image', reference_row)
        inputs_form.addRow('Motion reference', motion_row)
        inputs_form.addRow('Requested Background', background_row)
        inputs_form.addRow('Positive prompt', self.positive_prompt)
        inputs_form.addRow('Negative prompt', self.negative_prompt)
        self.inputs_group = inputs_group

        settings_group = QGroupBox('Generation settings · native WanGP contract')
        settings_form = QFormLayout(settings_group)
        self._configure_form_layout(settings_form)
        self.seed_spin = QSpinBox(); self.seed_spin.setRange(0, 2_147_483_647); self.seed_spin.setValue(18274)
        self.resolution_class_combo = QComboBox()
        self.aspect_ratio_combo = QComboBox()
        self.effective_resolution_label = QLabel('—')
        self.effective_resolution_label.setWordWrap(True)
        self.resolution_source_label = QLabel('—')
        self.resolution_source_label.setWordWrap(True)
        self.resolution_source_label.setStyleSheet('color: #8fc9a4;')
        self.frames_spin = QSpinBox(); self.frames_spin.setRange(5, 601); self.frames_spin.setValue(49)
        self.frames_spin.setSingleStep(4)
        self.effective_frames_label = QLabel('49')
        self.fps_spin = QDoubleSpinBox(); self.fps_spin.setRange(1.0, 120.0); self.fps_spin.setDecimals(3); self.fps_spin.setValue(24.0)
        self.effective_fps_label = QLabel('24 fps · requested')
        self.effective_fps_label.setWordWrap(True)
        self.steps_spin = QSpinBox(); self.steps_spin.setRange(1, 200); self.steps_spin.setValue(20)
        self.contract_preview = QPlainTextEdit()
        self.contract_preview.setReadOnly(True)
        self.contract_preview.setMaximumHeight(150)
        self.contract_preview.setPlaceholderText('Planned WanGP Job Summary')
        settings_form.addRow('Seed', self.seed_spin)
        settings_form.addRow('Resolution class', self.resolution_class_combo)
        settings_form.addRow('Aspect Ratio', self.aspect_ratio_combo)
        settings_form.addRow('WanGP Size', self.effective_resolution_label)
        settings_form.addRow('Resolution source', self.resolution_source_label)
        settings_form.addRow('Requested frames', self.frames_spin)
        settings_form.addRow('Executed frames', self.effective_frames_label)
        settings_form.addRow('Requested FPS', self.fps_spin)
        settings_form.addRow('Expected FPS', self.effective_fps_label)
        settings_form.addRow('Steps', self.steps_spin)
        settings_form.addRow('Summary', self.contract_preview)
        self.settings_group = settings_group

        self.resolution_class_combo.currentIndexChanged.connect(self._on_resolution_class_changed)
        self.aspect_ratio_combo.currentIndexChanged.connect(self._update_generation_contract)
        self.frames_spin.valueChanged.connect(self._update_generation_contract)
        self.fps_spin.valueChanged.connect(self._update_generation_contract)
        self.steps_spin.valueChanged.connect(self._update_generation_contract)
        self.motion_edit.textChanged.connect(self._update_generation_contract)
        self.template_edit.editingFinished.connect(self._reload_wan_resolution_options)
        self.working_dir_edit.editingFinished.connect(self._reload_wan_resolution_options)

        self.provider_combo.currentIndexChanged.connect(self._remember_current_generation_profile)
        self.model_combo.currentIndexChanged.connect(self._remember_current_generation_profile)
        self.reference_edit.textChanged.connect(self._remember_current_generation_profile)
        self.motion_edit.textChanged.connect(self._remember_current_generation_profile)
        self.positive_prompt.textChanged.connect(self._remember_current_generation_profile)
        self.negative_prompt.textChanged.connect(self._remember_current_generation_profile)
        self.seed_spin.valueChanged.connect(self._remember_current_generation_profile)
        self.resolution_class_combo.currentIndexChanged.connect(self._remember_current_generation_profile)
        self.aspect_ratio_combo.currentIndexChanged.connect(self._remember_current_generation_profile)
        self.frames_spin.valueChanged.connect(self._remember_current_generation_profile)
        self.fps_spin.valueChanged.connect(self._remember_current_generation_profile)
        self.steps_spin.valueChanged.connect(self._remember_current_generation_profile)

        actions = QHBoxLayout()
        self.validate_button = QPushButton('Validate')
        self.validate_button.clicked.connect(self._validate_request)
        self.generate_button = QPushButton('Generate')
        self.generate_button.clicked.connect(self._submit_job)
        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(self._cancel_job)
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.validate_button)
        actions.addWidget(self.generate_button)
        actions.addWidget(self.cancel_button)

        self.request_tabs = QTabWidget()
        self.request_tabs.setDocumentMode(True)

        generation_page = QWidget()
        generation_layout = QVBoxLayout(generation_page)
        generation_layout.setContentsMargins(4, 8, 4, 4)
        generation_layout.addWidget(self.provider_group)
        generation_layout.addWidget(self.inputs_group)
        generation_layout.addWidget(self.settings_group)
        generation_layout.addLayout(actions)
        generation_layout.addStretch(1)

        runtime_page = QWidget()
        runtime_layout = QVBoxLayout(runtime_page)
        runtime_layout.setContentsMargins(4, 8, 4, 4)
        runtime_layout.addWidget(self.runtime_group)
        runtime_layout.addStretch(1)

        profiles_page = QWidget()
        profiles_layout = QVBoxLayout(profiles_page)
        profiles_layout.setContentsMargins(4, 8, 4, 4)
        profiles_layout.addWidget(self.profiles_group)
        profiles_layout.addStretch(1)

        def scroll_page(page: QWidget) -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidget(page)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return scroll

        self.request_tabs.addTab(scroll_page(generation_page), 'Generation')
        self.request_tabs.addTab(scroll_page(runtime_page), 'WAN Runtime')
        self.request_tabs.addTab(scroll_page(profiles_page), 'Profiles')
        request_layout.addWidget(self.request_tabs, 1)
        splitter.addWidget(request_panel)

        status_panel = QWidget()
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(6, 0, 0, 0)

        status_group = QGroupBox('Current job')
        status_form = QFormLayout(status_group)
        self._configure_form_layout(status_form)
        self.job_id_label = QLabel('—')
        self.state_label = QLabel('idle')
        self.message_label = QLabel('No Job Started')
        self.message_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        status_form.addRow('Job ID', self.job_id_label)
        status_form.addRow('Status', self.state_label)
        status_form.addRow('Details', self.message_label)
        status_form.addRow('Progresso', self.progress_bar)
        self.executed_contract_label = QLabel('—')
        self.executed_contract_label.setWordWrap(True)
        status_form.addRow('Contratto', self.executed_contract_label)
        self.status_group = status_group

        output_group = QGroupBox('Output')
        output_layout = QVBoxLayout(output_group)
        self.output_path_label = QLabel('—')
        self.output_path_label.setWordWrap(True)
        self.open_output_button = QPushButton('Open Job Folder')
        self.open_output_button.clicked.connect(self._open_job_folder)
        self.open_output_button.setEnabled(False)
        self.import_button = QPushButton('Import MP4 into R1 Extraction')
        self.import_button.clicked.connect(self._import_result)
        self.import_button.setEnabled(False)
        output_layout.addWidget(self.output_path_label)
        output_layout.addWidget(self.open_output_button)
        output_layout.addWidget(self.import_button)
        self.output_group = output_group

        history_group = QGroupBox('Session history')
        history_layout = QVBoxLayout(history_group)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(['Job', 'Provider', 'Status', 'Progresso', 'Output'])
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        history_layout.addWidget(self.history_table)
        self.history_group = history_group

        self.status_tabs = QTabWidget()
        self.status_tabs.setDocumentMode(True)
        job_page = QWidget()
        job_layout = QVBoxLayout(job_page)
        job_layout.setContentsMargins(4, 8, 4, 4)
        job_layout.addWidget(self.status_group)
        job_layout.addWidget(self.output_group)
        job_layout.addStretch(1)
        history_page = QWidget()
        history_page_layout = QVBoxLayout(history_page)
        history_page_layout.setContentsMargins(4, 8, 4, 4)
        history_page_layout.addWidget(self.history_group, 1)
        self.status_tabs.addTab(job_page, 'Job / Output')
        self.status_tabs.addTab(history_page, 'History')
        status_layout.addWidget(self.status_tabs, 1)

        splitter.addWidget(status_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 580])
        root.addWidget(splitter, 1)

    @staticmethod
    def _configure_form_layout(form: QFormLayout) -> None:
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

    @staticmethod
    def _path_row(callback, directory: bool = False):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        button = QPushButton('Browse…')
        button.clicked.connect(callback)
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        return edit, container

    def _choose_path(self, edit: QLineEdit, title: str, file_filter: str = '', directory: bool = False) -> None:
        if directory:
            path = QFileDialog.getExistingDirectory(self, title, edit.text().strip())
        else:
            path, _ = QFileDialog.getOpenFileName(self, title, edit.text().strip(), file_filter or 'All Files (*)')
        if path:
            edit.setText(path)

    def _choose_python(self) -> None:
        self._choose_path(self.python_edit, 'Select Python 3.11 Interpreter', 'Python (python.exe python);;All Files (*)')

    def _choose_wangp_script(self) -> None:
        self._choose_path(self.wangp_edit, 'Select wgp.py', 'Python (*.py);;All Files (*)')
        script_text = self.wangp_edit.text().strip()
        if script_text:
            script_path = Path(script_text)
            if script_path.name.lower() == 'wgp.py':
                self.working_dir_edit.setText(str(script_path.parent))
        self._reload_wan_resolution_options()

    def _choose_template(self) -> None:
        self._choose_path(self.template_edit, 'Select WanGP JSON Template', 'JSON (*.json);;All Files (*)')
        self._reload_wan_resolution_options()

    def _choose_working_directory(self) -> None:
        self._choose_path(self.working_dir_edit, 'Select WanGP Folder', directory=True)
        self._reload_wan_resolution_options()

    def _choose_reference(self) -> None:
        self._choose_path(self.reference_edit, 'Select Reference Image', 'Images (*.png *.webp *.jpg *.jpeg);;All Files (*)')

    def _choose_motion_reference(self) -> None:
        self._choose_path(self.motion_edit, 'Select Motion Reference Video', 'Video (*.mp4 *.m4v *.mov *.avi *.webm);;All Files (*)')
        self._update_generation_contract()

    def _resolved_wangp_root(self) -> Path | None:
        working_text = self.working_dir_edit.text().strip()
        if working_text:
            working_path = Path(working_text).expanduser()
            if working_path.is_dir():
                return working_path
        script_text = self.wangp_edit.text().strip()
        if script_text:
            script_path = Path(script_text).expanduser()
            if script_path.name.lower() == 'wgp.py':
                return script_path.parent
        return None

    def _reload_wan_resolution_options(self) -> None:
        previous_class = str(self.resolution_class_combo.currentData() or '') if hasattr(self, 'resolution_class_combo') else ''
        previous_ratio = str(self.aspect_ratio_combo.currentData() or '') if hasattr(self, 'aspect_ratio_combo') else ''
        root = self._resolved_wangp_root()
        self._resolution_options = merged_resolution_options(
            root,
            self.template_edit.text().strip() or None,
        )
        if not hasattr(self, 'resolution_class_combo'):
            return

        template_option = template_resolution_option(self.template_edit.text().strip() or None)
        target_class = previous_class
        target_ratio = previous_ratio
        if not target_class and template_option is not None:
            exact = next(
                (
                    option for option in self._resolution_options
                    if option.width == template_option.width and option.height == template_option.height
                ),
                None,
            )
            if exact is not None:
                target_class, target_ratio = exact.resolution_class, exact.aspect_ratio
        if not target_class:
            target_class, target_ratio = '480p', '16:9'

        self.resolution_class_combo.blockSignals(True)
        self.resolution_class_combo.clear()
        classes: list[str] = []
        for option in self._resolution_options:
            if option.resolution_class not in classes:
                classes.append(option.resolution_class)
        for resolution_class in classes:
            self.resolution_class_combo.addItem(resolution_class, resolution_class)
        index = self.resolution_class_combo.findData(target_class)
        self.resolution_class_combo.setCurrentIndex(index if index >= 0 else 0)
        self.resolution_class_combo.blockSignals(False)
        self._populate_aspect_ratios(preferred_ratio=target_ratio)
        self._update_generation_contract()

    def _populate_aspect_ratios(self, *, preferred_ratio: str = '') -> None:
        resolution_class = str(self.resolution_class_combo.currentData() or '')
        current_ratio = preferred_ratio or str(self.aspect_ratio_combo.currentData() or '')
        options = [option for option in self._resolution_options if option.resolution_class == resolution_class]
        self.aspect_ratio_combo.blockSignals(True)
        self.aspect_ratio_combo.clear()
        for option in options:
            self.aspect_ratio_combo.addItem(f'{option.aspect_ratio} · {option.value}', option.aspect_ratio)
        index = self.aspect_ratio_combo.findData(current_ratio)
        self.aspect_ratio_combo.setCurrentIndex(index if index >= 0 else 0)
        self.aspect_ratio_combo.blockSignals(False)

    def _on_resolution_class_changed(self, *_args) -> None:
        self._populate_aspect_ratios()
        self._update_generation_contract()

    def _current_resolution_option(self) -> WanResolutionOption:
        resolution_class = str(self.resolution_class_combo.currentData() or '')
        aspect_ratio = str(self.aspect_ratio_combo.currentData() or '')
        option = option_for_selection(self._resolution_options, resolution_class, aspect_ratio)
        if option is None:
            raise ValueError('No valid WanGP resolution selected.')
        return option

    def _probe_motion_fps(self) -> float | None:
        path_text = self.motion_edit.text().strip()
        if not path_text:
            return None
        path = Path(path_text).expanduser()
        cache_key = str(path.resolve()) if path.exists() else str(path)
        if cache_key in self._motion_fps_cache:
            return self._motion_fps_cache[cache_key]
        if not path.is_file():
            self._motion_fps_cache[cache_key] = None
            return None
        source = VideoSource()
        try:
            metadata = source.open(path)
            fps = float(metadata.fps) if metadata.fps > 0 else None
        except VideoOpenError:
            fps = None
        finally:
            source.close()
        self._motion_fps_cache[cache_key] = fps
        return fps

    def _generation_contract(self) -> dict:
        option = self._current_resolution_option()
        requested_frames = int(self.frames_spin.value())
        effective_frames = normalize_wan_frame_count(requested_frames)
        force_fps = read_force_fps(self.template_edit.text().strip() or None)
        fps_contract = resolve_fps_contract(
            self.fps_spin.value(),
            force_fps,
            self._probe_motion_fps(),
        )
        return {
            'resolution': option.to_dict(),
            'frames': {
                'requested': requested_frames,
                'effective': effective_frames,
                'rule': '4n+1_floor',
            },
            'fps': fps_contract.to_dict(),
            'steps': int(self.steps_spin.value()),
            'prompt_profile_name': str(self.prompt_profile_name),
            'prompt_builder_state': dict(self.prompt_builder_state),
        }

    def _update_generation_contract(self, *_args) -> None:
        if not self._resolution_options or not hasattr(self, 'contract_preview'):
            return
        try:
            contract = self._generation_contract()
        except Exception as exc:
            self.contract_preview.setPlainText(str(exc))
            return
        resolution = contract['resolution']
        frames = contract['frames']
        fps = contract['fps']
        self.effective_resolution_label.setText(
            f"{resolution['width']} × {resolution['height']} · {resolution['aspect_ratio']} · {resolution['resolution_class']}"
        )
        source = str(resolution.get('source', 'builtin'))
        if source == 'builtin':
            source_text = 'built-in R5b1c table'
        elif source.endswith('resolutions.json'):
            source_text = f'WanGP resolutions.json: {source}'
        else:
            source_text = f'preset: {source}'
        self.resolution_source_label.setText(source_text)
        self.effective_frames_label.setText(
            str(frames['effective']) if frames['effective'] == frames['requested']
            else f"{frames['effective']} · normalized from {frames['requested']}"
        )
        if fps['effective_fps'] is None:
            fps_text = 'from control video · not detectable yet'
        else:
            fps_text = f"{fps['effective_fps']:.3f} fps · {fps['source']}"
        self.effective_fps_label.setText(fps_text)
        self.contract_preview.setPlainText(
            '\n'.join([
                f"Resolution: {resolution['resolution_class']} · {resolution['aspect_ratio']} → {resolution['value']}",
                f"Frames: requested {frames['requested']} → executed {frames['effective']} ({frames['rule']})",
                f"FPS: requested {fps['requested_fps']:.3f} → expected {fps_text}",
                f"force_fps preset: {fps['force_fps'] or '(not set)'}",
                f"Steps: {contract['steps']}",
            ])
        )

    def capture_generation_profile(self) -> dict:
        """Public R5e7 hook used by Calibration Lab / Prompt Builder without exposing widget internals."""
        return self._capture_generation_profile_data()

    def apply_generation_profile(self, data: dict, *, persist_last: bool = True) -> None:
        """Public R5e7 hook used to load a calibrated, variant or prompt profile into Generate."""
        if isinstance(data, dict):
            self._apply_generation_profile_data(data, persist_last=persist_last)

    def save_generation_profile(self, name: str, data: dict) -> None:
        normalized = str(name).strip()
        if not normalized:
            raise ValueError('The generation profile name cannot be empty.')
        self.profile_store.set_profile('generation', normalized, dict(data))
        self._refresh_generation_profiles_combo(normalized)

    def _capture_generation_profile_data(self) -> dict:
        resolution_class = self.resolution_class_combo.currentData()
        aspect_ratio = self.aspect_ratio_combo.currentData()
        return {
            'provider_id': str(self.provider_combo.currentData()),
            'model_id': str(self.model_combo.currentData()),
            'reference_image': self.reference_edit.text().strip(),
            'motion_video': self.motion_edit.text().strip(),
            'positive_prompt': self.positive_prompt.toPlainText().strip(),
            'negative_prompt': self.negative_prompt.toPlainText().strip(),
            'requested_background_rgb': list(self.requested_background_rgb),
            'seed': int(self.seed_spin.value()),
            'resolution_class': str(resolution_class or ''),
            'aspect_ratio': str(aspect_ratio or ''),
            'frames': int(self.frames_spin.value()),
            'fps': float(self.fps_spin.value()),
            'steps': int(self.steps_spin.value()),
            'prompt_profile_name': str(self.prompt_profile_name),
            'prompt_builder_state': dict(self.prompt_builder_state),
        }

    def _apply_generation_profile_data(self, data: dict, *, persist_last: bool = True) -> None:
        provider_id = str(data.get('provider_id', self.provider_combo.currentData()))
        provider_index = self.provider_combo.findData(provider_id)
        if provider_index >= 0:
            self.provider_combo.setCurrentIndex(provider_index)
            self._refresh_provider_ui()
        self.reference_edit.setText(str(data.get('reference_image', self.reference_edit.text())))
        self.motion_edit.setText(str(data.get('motion_video', self.motion_edit.text())))
        self.positive_prompt.setPlainText(str(data.get('positive_prompt', self.positive_prompt.toPlainText())))
        self.negative_prompt.setPlainText(str(data.get('negative_prompt', self.negative_prompt.toPlainText())))
        rgb = data.get('requested_background_rgb', self.requested_background_rgb)
        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
            self.requested_background_rgb = tuple(int(v) for v in rgb)
            self._update_requested_background_swatch()
        self.seed_spin.setValue(int(data.get('seed', self.seed_spin.value())))
        resolution_class = str(data.get('resolution_class', self.resolution_class_combo.currentData() or ''))
        aspect_ratio = str(data.get('aspect_ratio', self.aspect_ratio_combo.currentData() or ''))
        res_idx = self.resolution_class_combo.findData(resolution_class)
        if res_idx >= 0:
            self.resolution_class_combo.setCurrentIndex(res_idx)
        aspect_idx = self.aspect_ratio_combo.findData(aspect_ratio)
        if aspect_idx >= 0:
            self.aspect_ratio_combo.setCurrentIndex(aspect_idx)
        self.frames_spin.setValue(int(data.get('frames', self.frames_spin.value())))
        self.fps_spin.setValue(float(data.get('fps', self.fps_spin.value())))
        self.steps_spin.setValue(int(data.get('steps', self.steps_spin.value())))
        self.prompt_profile_name = str(data.get('prompt_profile_name', self.prompt_profile_name or ''))
        builder_state = data.get('prompt_builder_state')
        if isinstance(builder_state, dict):
            self.prompt_builder_state = dict(builder_state)
        model_id = str(data.get('model_id', self.model_combo.currentData()))
        model_index = self.model_combo.findData(model_id)
        if model_index >= 0:
            self.model_combo.setCurrentIndex(model_index)
        self._update_generation_contract()
        if persist_last:
            self.profile_store.set_last_used('generation', self._capture_generation_profile_data())

    def _remember_current_generation_profile(self, *_args) -> None:
        try:
            self.profile_store.set_last_used('generation', self._capture_generation_profile_data())
        except Exception:
            return

    def _refresh_generation_profiles_combo(self, selected_name: str | None = None) -> None:
        names = self.profile_store.list_profiles('generation')
        self.generation_profile_combo.clear()
        self.generation_profile_combo.addItems(names)
        if selected_name and selected_name in names:
            self.generation_profile_combo.setCurrentText(selected_name)

    def _load_last_used_generation_profile(self) -> None:
        data = self.profile_store.get_last_used('generation')
        if data:
            self._apply_generation_profile_data(data, persist_last=False)

    def _save_current_generation_profile_as(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, 'Save Generation Profile', 'Profile name:')
        if not ok:
            return
        normalized = name.strip()
        if not normalized:
            return
        self.profile_store.set_profile('generation', normalized, self._capture_generation_profile_data())
        self._refresh_generation_profiles_combo(normalized)
        self.status_message.emit(f'Generation profile saved: {normalized}')

    def _load_selected_generation_profile(self) -> None:
        name = self.generation_profile_combo.currentText().strip()
        if not name:
            return
        data = self.profile_store.get_profile('generation', name)
        if data is None:
            QMessageBox.information(self, 'Profile Not Found', 'The selected profile is not available.')
            self._refresh_generation_profiles_combo()
            return
        self._apply_generation_profile_data(data, persist_last=True)
        self.status_message.emit(f'Generation profile loaded: {name}')

    def _delete_selected_generation_profile(self) -> None:
        name = self.generation_profile_combo.currentText().strip()
        if not name:
            return
        answer = QMessageBox.question(self, 'Delete Profile', f'Delete profile "{name}"?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.profile_store.delete_profile('generation', name)
        self._refresh_generation_profiles_combo()
        self.status_message.emit(f'Generation profile deleted: {name}')

    def snapshot_state(self) -> dict:
        # Runtime bridge configuration has its own canonical persistence in
        # local_wangp.json. Duplicating it into app/project state can restore
        # stale interpreter paths after the Runtime Manager repairs/installs
        # the dedicated Python 3.11 environment.
        return {
            'generation_profile': self._capture_generation_profile_data(),
        }

    def apply_state(self, state: dict) -> None:
        if not isinstance(state, dict):
            return
        # local_config from historical app/project snapshots is intentionally
        # ignored. local_wangp.json is the single source of truth.
        self._reload_wan_resolution_options()
        profile = state.get('generation_profile')
        if isinstance(profile, dict):
            self._apply_generation_profile_data(profile, persist_last=False)

    def _config_from_ui(self) -> LocalWanGPConfig:
        return LocalWanGPConfig(
            python_executable=self.python_edit.text().strip(),
            wangp_script=self.wangp_edit.text().strip(),
            settings_template=self.template_edit.text().strip(),
            working_directory=self.working_dir_edit.text().strip(),
            verbose=self.verbose_spin.value(),
            strict_python_311=self.strict_python_checkbox.isChecked(),
            require_template=self.require_template_checkbox.isChecked(),
        )

    def _load_local_config_into_ui(self) -> None:
        config = self.local_config
        self.python_edit.setText(config.python_executable)
        self.wangp_edit.setText(config.wangp_script)
        self.template_edit.setText(config.settings_template)
        self.working_dir_edit.setText(config.working_directory)
        self.verbose_spin.setValue(config.verbose)
        self.strict_python_checkbox.setChecked(config.strict_python_311)
        self.require_template_checkbox.setChecked(config.require_template)

    def reload_local_runtime_config(self) -> None:
        self.local_config = LocalWanGPConfig.load()
        self.local_provider.update_config(self.local_config)
        self._load_local_config_into_ui()
        self._reload_wan_resolution_options()
        self.status_message.emit('WanGP runtime configuration reloaded from Runtime Manager.')

    def _save_local_config(self) -> None:
        self.local_config = self._config_from_ui()
        self.local_provider.update_config(self.local_config)

        resolved_working_directory, warning = self.local_provider.resolve_working_directory()
        if (
            self.local_provider.uses_standard_wangp_layout()
            and resolved_working_directory.is_dir()
            and (resolved_working_directory / 'models' / '_settings.json').is_file()
            and Path(self.local_config.working_directory).expanduser() != resolved_working_directory
        ):
            self.local_config.working_directory = str(resolved_working_directory)
            self.working_dir_edit.setText(str(resolved_working_directory))
            self.local_provider.update_config(self.local_config)

        path = self.local_config.save()
        detail = f'WanGP configuration saved: {path}'
        if warning:
            detail += f' — {warning}'
        self.status_message.emit(detail)
        self._reload_wan_resolution_options()

    def _run_health_check(self) -> None:
        self._save_local_config()
        report = self.local_provider.health_check()
        self.health_report.setPlainText(report.summary())
        if report.available:
            QMessageBox.information(self, 'Health check', 'The WanGP bridge is ready.')
        else:
            QMessageBox.warning(self, 'Health check', report.summary())

    def _refresh_provider_ui(self) -> None:
        provider_id = str(self.provider_combo.currentData())
        provider = self.registry.get(provider_id)
        caps = provider.get_capabilities()
        enabled = [name for name, value in caps.to_dict().items() if value]
        self.capabilities_label.setText(', '.join(enabled) or 'none')
        self.model_combo.clear()
        is_local = provider_id == 'local_wangp'
        self.runtime_group.setVisible(is_local)
        self.motion_edit.setEnabled(caps.motion_reference)
        if is_local:
            self.model_combo.addItem('Model defined by the WanGP preset', 'wangp_template_model')
            self.privacy_label.setText('Local — reference files remain on this computer.')
            self.generate_button.setText('Generate with WanGP')
        else:
            self.model_combo.addItem('Mock Sprite Video v1', 'mock_sprite_video_v1')
            self.privacy_label.setText('Local mock — no files are uploaded externally.')
            self.generate_button.setText('Generate Mock')

    def _build_request(self, *, dry_run: bool = False) -> GenerationRequest:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        provider_id = str(self.provider_combo.currentData())
        job_id = f"{'dryrun' if dry_run else provider_id}_{timestamp}"
        contract = self._generation_contract()
        resolution = contract['resolution']
        frames = contract['frames']
        return GenerationRequest(
            job_id=job_id,
            provider=provider_id,
            model=str(self.model_combo.currentData()),
            reference_image=self.reference_edit.text().strip() or None,
            motion_video=self.motion_edit.text().strip() or None,
            positive_prompt=self.positive_prompt.toPlainText().strip(),
            negative_prompt=self.negative_prompt.toPlainText().strip(),
            seed=self.seed_spin.value(),
            width=int(resolution['width']),
            height=int(resolution['height']),
            frames=int(frames['effective']),
            fps=self.fps_spin.value(),
            steps=self.steps_spin.value(),
            metadata={
                'dry_run': dry_run,
                'requested_background_rgb': list(self.requested_background_rgb),
                'background_mode': 'solid_chroma',
                'wan_contract': contract,
                'requested_resolution_class': resolution['resolution_class'],
                'requested_aspect_ratio': resolution['aspect_ratio'],
                'requested_frames': frames['requested'],
                'effective_frames': frames['effective'],
                'requested_fps': contract['fps']['requested_fps'],
                'effective_fps': contract['fps']['effective_fps'],
                'fps_source': contract['fps']['source'],
                'prompt_profile_name': str(self.prompt_profile_name),
                'prompt_builder_state': dict(self.prompt_builder_state),
            },
        )

    def _choose_requested_background(self) -> None:
        color = QColorDialog.getColor(QColor(*self.requested_background_rgb), self, 'Requested Background Color')
        if not color.isValid():
            return
        self.requested_background_rgb = (color.red(), color.green(), color.blue())
        self._update_requested_background_swatch()

    def _update_requested_background_swatch(self) -> None:
        r, g, b = self.requested_background_rgb
        self.background_swatch.setStyleSheet(
            f'QFrame {{ background: rgb({r}, {g}, {b}); border: 1px solid #555; }}'
        )
        self.background_swatch.setToolTip(f'RGB ({r}, {g}, {b}) · #{r:02X}{g:02X}{b:02X}')

    def _validate_request(self) -> None:
        try:
            if str(self.provider_combo.currentData()) == 'local_wangp':
                self._save_local_config()
            request = self._build_request()
            self.registry.get(request.provider).validate_request(request)
        except Exception as exc:
            QMessageBox.warning(self, 'Invalid Request', str(exc))
            return
        contract = request.metadata.get('wan_contract', {})
        resolution = contract.get('resolution', {})
        frames = contract.get('frames', {})
        fps = contract.get('fps', {})
        detail = (
            f"The request is compatible with {self.registry.get(request.provider).display_name}.\n\nResolved request: {resolution.get('value', f'{request.width}x{request.height}')}\nFrame: {frames.get('requested', request.frames)} requested → {request.frames} executed\nExpected FPS: {fps.get('effective_fps')} · source {fps.get('source', 'request')}"
        )
        QMessageBox.information(self, 'Validation completed', detail)

    def _submit_dry_run(self) -> None:
        if str(self.provider_combo.currentData()) != 'local_wangp':
            return
        self._save_local_config()
        self._submit(dry_run=True)

    def _submit_job(self) -> None:
        if str(self.provider_combo.currentData()) == 'local_wangp':
            self._save_local_config()
        self._submit(dry_run=False)

    def _submit(self, *, dry_run: bool) -> None:
        if self.current_job_id:
            snapshot = self.manager.get_snapshot(self.current_job_id)
            if snapshot and snapshot.state not in {'completed', 'failed', 'cancelled'}:
                QMessageBox.information(self, 'Active job', 'Wait for or cancel the current job.')
                return
        try:
            request = self._build_request(dry_run=dry_run)
            self.current_job_id = self.manager.submit(request)
            self.job_started.emit(self.current_job_id)
        except Exception as exc:
            QMessageBox.critical(self, 'Job Start Error', str(exc))
            return
        self.last_video_path = None
        self.job_id_label.setText(self.current_job_id)
        self.executed_contract_label.setText(self.contract_preview.toPlainText().replace('\n', ' · '))
        self.generate_button.setEnabled(False)
        self.dry_run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.import_button.setEnabled(False)
        self.open_output_button.setEnabled(True)
        self.poll_timer.start()
        self.status_message.emit(f'Job started: {self.current_job_id}')
        self._refresh_history()

    def _cancel_job(self) -> None:
        if self.current_job_id:
            self.manager.cancel(self.current_job_id)

    def _poll_current_job(self) -> None:
        if not self.current_job_id:
            self.poll_timer.stop()
            return
        snapshot = self.manager.get_snapshot(self.current_job_id)
        if snapshot is None:
            return
        self.state_label.setText(snapshot.state)
        self.message_label.setText(snapshot.message)
        self.progress_bar.setValue(int(round(snapshot.progress * 1000)))
        self.output_path_label.setText(snapshot.job_directory)
        self._refresh_history()
        if snapshot.state in {'completed', 'failed', 'cancelled'}:
            self.poll_timer.stop()
            self.generate_button.setEnabled(True)
            self.dry_run_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            if snapshot.result and snapshot.result.is_completed and snapshot.result.video_path:
                self.last_video_path = snapshot.result.video_path
                self.output_path_label.setText(snapshot.result.video_path)
                self.import_button.setEnabled(True)
                metadata = snapshot.result.metadata
                actual_width = metadata.get('actual_width', metadata.get('width'))
                actual_height = metadata.get('actual_height', metadata.get('height'))
                actual_frames = metadata.get('actual_frames', metadata.get('frames'))
                actual_fps = metadata.get('actual_fps', metadata.get('fps'))
                requested_frames = metadata.get('requested_frames', '—')
                self.executed_contract_label.setText(
                    f'Actual output: {actual_width}x{actual_height} · {actual_frames} frame · {actual_fps} fps | requested frames: {requested_frames}'
                )
                self.status_message.emit(f'Generation completed: {snapshot.provider}')
            elif snapshot.result and snapshot.result.metadata.get('dry_run') and snapshot.state == 'completed':
                self.status_message.emit('WanGP dry-run completed successfully.')
                self.message_label.setText('Dry-run completed: job and runtime accepted.')
            elif snapshot.result:
                self.status_message.emit(snapshot.result.error_message or snapshot.state)
            self.job_finished.emit(snapshot.to_dict())

    def _refresh_history(self) -> None:
        snapshots = self.manager.list_snapshots()
        self.history_table.setRowCount(len(snapshots))
        for row, snapshot in enumerate(snapshots):
            values = [
                snapshot.job_id,
                snapshot.provider,
                snapshot.state,
                f'{snapshot.progress * 100:.0f}%',
                snapshot.result.video_path if snapshot.result and snapshot.result.video_path else snapshot.job_directory,
            ]
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _open_job_folder(self) -> None:
        if not self.current_job_id:
            return
        snapshot = self.manager.get_snapshot(self.current_job_id)
        if snapshot:
            QDesktopServices.openUrl(QUrl.fromLocalFile(snapshot.job_directory))

    def _import_result(self) -> None:
        if not self.last_video_path:
            return
        path = Path(self.last_video_path)
        if not path.exists() or path.stat().st_size <= 0:
            QMessageBox.critical(self, 'Missing Output', 'The video file is not available.')
            return
        self.video_ready.emit(str(path))

    def shutdown(self) -> None:
        self.poll_timer.stop()
        self.manager.shutdown()
