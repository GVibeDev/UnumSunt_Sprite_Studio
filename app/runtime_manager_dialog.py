from __future__ import annotations

from pathlib import Path
import webbrowser

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.runtime_installer import (
    RuntimeInstallOptions,
    RuntimeInstallState,
    RuntimeInstaller,
    RuntimeInstallError,
    load_runtime_components_manifest,
)
from app.runtime_preflight import RuntimePreflightConfig, STATUS_BLOCKED, run_runtime_preflight
from app.runtime_adoption import (
    ExternalRuntimeCandidate,
    adopt_external_runtime,
    candidate_from_current_bridge,
    discover_existing_runtimes,
    validate_external_candidate,
)

from app.version import APP_VERSION

class RuntimeInstallWorker(QObject):
    progress = Signal(str, float, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, config: RuntimePreflightConfig, options: RuntimeInstallOptions) -> None:
        super().__init__()
        self.config = config
        self.options = options
        self._cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            installer = RuntimeInstaller(
                self.config,
                progress=lambda phase, fraction, message: self.progress.emit(phase, fraction, message),
                cancelled=lambda: self._cancelled,
            )
            state = installer.install(self.options)
            self.finished.emit(state)
        except Exception as exc:
            self.failed.emit(str(exc))

    @Slot()
    def cancel(self) -> None:
        self._cancelled = True


class RuntimeManagerDialog(QDialog):
    runtime_config_changed = Signal()
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f'Local AI Runtime Manager · {APP_VERSION}')
        self.resize(1040, 820)
        self.config = RuntimePreflightConfig.load()
        self.manifest = load_runtime_components_manifest()
        self._thread: QThread | None = None
        self._worker: RuntimeInstallWorker | None = None
        self._discovered_runtimes: list[ExternalRuntimeCandidate] = []
        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            f'Installs and manages Sprite Studio’s private AI runtime. The preflight {APP_VERSION} remains mandatory: CUDA/driver, disk space, and paths must be valid; GPU model, VRAM, and RAM remain diagnostic.'
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        paths_group = QGroupBox('Paths')
        paths = QGridLayout(paths_group)
        paths.addWidget(QLabel('AI Runtime:'), 0, 0)
        self.runtime_edit = QLineEdit(self.config.runtime_root)
        paths.addWidget(self.runtime_edit, 0, 1)
        runtime_browse = QPushButton("Browse…")
        runtime_browse.clicked.connect(lambda: self._browse(self.runtime_edit))
        paths.addWidget(runtime_browse, 0, 2)
        paths.addWidget(QLabel('AI Models:'), 1, 0)
        self.models_edit = QLineEdit(self.config.model_root)
        paths.addWidget(self.models_edit, 1, 1)
        models_browse = QPushButton("Browse…")
        models_browse.clicked.connect(lambda: self._browse(self.models_edit))
        paths.addWidget(models_browse, 1, 2)
        root.addWidget(paths_group)

        adoption = QGroupBox('Existing Runtime · no download / no relocation')
        adoption_layout = QGridLayout(adoption)
        self.runtime_discovery_combo = QComboBox()
        self.runtime_discovery_combo.setMinimumWidth(520)
        self.runtime_discovery_combo.addItem('No Runtime Detected')
        adoption_layout.addWidget(self.runtime_discovery_combo, 0, 0, 1, 3)
        detect_btn = QPushButton('Detect Existing Installations')
        detect_btn.clicked.connect(self.detect_existing_runtimes)
        adoption_layout.addWidget(detect_btn, 1, 0)
        adopt_btn = QPushButton('Adopt Selected')
        adopt_btn.clicked.connect(self.adopt_selected_runtime)
        adoption_layout.addWidget(adopt_btn, 1, 1)
        manual_btn = QPushButton("Adopt manually…")
        manual_btn.clicked.connect(self.adopt_runtime_manually)
        adoption_layout.addWidget(manual_btn, 1, 2)
        note = QLabel(
            'Adoption records the existing Python 3.11, wgp.py, and model paths. It does not rename, copy, delete, or update the external runtime.'
        )
        note.setWordWrap(True)
        adoption_layout.addWidget(note, 2, 0, 1, 3)
        root.addWidget(adoption)

        components = QGroupBox('Components')
        comp_layout = QVBoxLayout(components)
        self.runtime_check = QCheckBox('Base runtime · Miniconda + Python 3.11.14 + PyTorch 2.10/cu130 + WanGP')
        self.runtime_check.setChecked(True)
        self.animate_check = QCheckBox("Wan 2.2 Animate 14B · checkpoint Quanto BF16 INT8 (~17.9 GB)")
        self.animate_check.setChecked(True)
        self.krea_check = QCheckBox("Krea 2 Turbo · WanGP Quanto BF16 INT8 (~13.5 GB)")
        self.krea_check.setChecked(True)
        comp_layout.addWidget(self.runtime_check)
        comp_layout.addWidget(self.animate_check)
        comp_layout.addWidget(self.krea_check)
        root.addWidget(components)

        licenses = QGroupBox('Licenses / Access')
        license_layout = QFormLayout(licenses)
        self.anaconda_tos = QCheckBox('I have read and accept the applicable Anaconda/Miniconda terms for this installation')
        license_layout.addRow(self.anaconda_tos)
        self.krea_license = QCheckBox('I have read and accept the Krea 2 Community License + AUP for this component')
        license_layout.addRow(self.krea_license)
        self.hf_token_edit = QLineEdit()
        self.hf_token_edit.setEchoMode(QLineEdit.Password)
        self.hf_token_edit.setPlaceholderText('hf_… · optional; used only in the current process and never stored')
        license_layout.addRow('HF token (optional):', self.hf_token_edit)
        links = QHBoxLayout()
        krea_access = QPushButton('Open Krea 2 Access Page')
        krea_access.clicked.connect(lambda: webbrowser.open(self.manifest.models["krea2_turbo"].access_url))
        links.addWidget(krea_access)
        krea_license = QPushButton('Open Krea 2 License')
        krea_license.clicked.connect(lambda: webbrowser.open(self.manifest.models["krea2_turbo"].license_url))
        links.addWidget(krea_license)
        krea_aup = QPushButton('Open Krea 2 AUP')
        krea_aup.clicked.connect(lambda: webbrowser.open(self.manifest.models["krea2_turbo"].aup_url))
        links.addWidget(krea_aup)
        links.addStretch(1)
        license_layout.addRow(links)
        root.addWidget(licenses)

        self.summary = QLabel('Status Not Checked')
        self.summary.setAlignment(Qt.AlignCenter)
        self.summary.setStyleSheet("QLabel { color: white; background: #343a46; padding: 8px; font-weight: 700; }")
        root.addWidget(self.summary)

        self.status_table = QTableWidget(0, 3)
        self.status_table.setHorizontalHeaderLabels(['Component', 'Status', "Details"])
        self.status_table.verticalHeader().setVisible(False)
        self.status_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.status_table, 2)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(600)
        root.addWidget(self.log, 2)

        buttons = QHBoxLayout()
        self.preflight_btn = QPushButton("Preflight")
        self.preflight_btn.clicked.connect(self.run_preflight)
        buttons.addWidget(self.preflight_btn)
        self.health_btn = QPushButton("Health Check")
        self.health_btn.clicked.connect(self.refresh_status)
        buttons.addWidget(self.health_btn)
        self.install_btn = QPushButton('Install Selected')
        self.install_btn.clicked.connect(lambda: self.start_install(repair=False))
        buttons.addWidget(self.install_btn)
        self.repair_btn = QPushButton('Repair / Update Runtime')
        self.repair_btn.clicked.connect(lambda: self.start_install(repair=True))
        buttons.addWidget(self.repair_btn)
        self.remove_animate_btn = QPushButton('Remove Animate')
        self.remove_animate_btn.clicked.connect(lambda: self.remove_model("wan_animate"))
        buttons.addWidget(self.remove_animate_btn)
        self.remove_krea_btn = QPushButton('Remove Krea 2')
        self.remove_krea_btn.clicked.connect(lambda: self.remove_model("krea2_turbo"))
        buttons.addWidget(self.remove_krea_btn)
        buttons.addStretch(1)
        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_install)
        buttons.addWidget(self.cancel_btn)
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def _browse(self, edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, 'Select Folder', edit.text().strip() or str(Path.home()))
        if selected:
            edit.setText(selected)

    def detect_existing_runtimes(self) -> None:
        self._discovered_runtimes = discover_existing_runtimes(
            extra_roots=[self.runtime_edit.text().strip()] if self.runtime_edit.text().strip() else [],
        )
        self.runtime_discovery_combo.clear()
        if not self._discovered_runtimes:
            self.runtime_discovery_combo.addItem('No compatible runtime detected in known paths')
            self.log.appendPlainText(
                "No runtime was detected automatically. Use 'Adopt Manually…' without renaming existing folders."
            )
            return
        for candidate in self._discovered_runtimes:
            self.runtime_discovery_combo.addItem(candidate.label)
        self.log.appendPlainText(f'Detected {len(self._discovered_runtimes)} runtime candidates. No files were modified.')

    def _adopt_candidate(self, candidate: ExternalRuntimeCandidate) -> None:
        try:
            state = adopt_external_runtime(candidate)
        except Exception as exc:
            QMessageBox.critical(self, 'Runtime Cannot Be Adopted', str(exc))
            self.log.appendPlainText('Adoption failed: ' + str(exc))
            return
        self.config = RuntimePreflightConfig.load()
        self.runtime_edit.setText(self.config.runtime_root)
        self.models_edit.setText(self.config.model_root)
        self.log.appendPlainText(
            f'External runtime adopted without downloads or relocation:\nPython: {state.python_executable}\nWanGP: {state.wangp_script}\nModels: {state.model_root}'
        )
        self.runtime_config_changed.emit()
        self.refresh_status()
        QMessageBox.information(
            self,
            'Runtime Adopted',
            'Existing runtime registered. No folder was renamed or modified.'
        )

    def adopt_selected_runtime(self) -> None:
        index = self.runtime_discovery_combo.currentIndex()
        if index < 0 or index >= len(self._discovered_runtimes):
            QMessageBox.information(self, 'Existing Runtime', 'Run detection first or use manual adoption.')
            return
        self._adopt_candidate(self._discovered_runtimes[index])

    def adopt_runtime_manually(self) -> None:
        current = candidate_from_current_bridge()
        start_python = current.python_executable if current else str(Path.home())
        python, _ = QFileDialog.getOpenFileName(self, 'Select WanGP Runtime Python 3.11', start_python, 'Python executable (python.exe);;All Files (*)')
        if not python:
            return
        start_wgp = current.wangp_script if current else str(Path(python).parent)
        wgp, _ = QFileDialog.getOpenFileName(self, 'Select wgp.py from the WanGP Installation', start_wgp, 'WanGP launcher (wgp.py);;Python files (*.py);;All Files (*)')
        if not wgp:
            return
        wgp_root = Path(wgp).parent
        default_models = current.model_root if current and current.model_root else str(wgp_root / 'ckpts' if (wgp_root / 'ckpts').exists() else wgp_root)
        models = QFileDialog.getExistingDirectory(self, 'Select Existing Model Folder', default_models)
        if not models:
            models = default_models
        settings = current.settings_template if current else ""
        candidate = ExternalRuntimeCandidate(
            python_executable=python,
            wangp_script=wgp,
            working_directory=str(wgp_root),
            settings_template=settings,
            model_root=models,
            source='manual adoption',
        )
        self._adopt_candidate(candidate)

    def _current_config(self) -> RuntimePreflightConfig:
        return RuntimePreflightConfig(
            runtime_root=self.runtime_edit.text().strip(),
            model_root=self.models_edit.text().strip(),
        )

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.preflight_btn, self.health_btn, self.install_btn, self.repair_btn,
            self.remove_animate_btn, self.remove_krea_btn,
            self.runtime_edit, self.models_edit,
        ):
            widget.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)

    def run_preflight(self) -> None:
        config = self._current_config()
        report = run_runtime_preflight(config)
        config.save()
        self.log.appendPlainText(report.summary())
        color = "#8b3136" if report.status == STATUS_BLOCKED else "#31784b"
        self.summary.setText(f"PREFLIGHT: {report.status}")
        self.summary.setStyleSheet(f"QLabel {{ color:white; background:{color}; padding:8px; font-weight:700; }}")

    def refresh_status(self) -> None:
        config = self._current_config()
        state = RuntimeInstallState.load()
        if state.ownership == "external" and state.python_executable and state.wangp_script:
            candidate = ExternalRuntimeCandidate(
                python_executable=state.python_executable,
                wangp_script=state.wangp_script,
                working_directory=state.wangp_root or state.runtime_root,
                settings_template=state.settings_template,
                model_root=state.model_root,
                source='external runtime adopted',
            )
            try:
                bridge_report, _ = validate_external_candidate(candidate)
            except Exception as exc:
                self.summary.setText('EXTERNAL RUNTIME: ERROR')
                self.log.appendPlainText(str(exc))
                return
            self.status_table.setRowCount(len(bridge_report.checks))
            for row, item in enumerate(bridge_report.checks):
                self.status_table.setItem(row, 0, QTableWidgetItem(item.name))
                status_item = QTableWidgetItem("OK" if item.ok else "FAIL")
                status_item.setForeground(QColor("white"))
                status_item.setBackground(QColor("#31784b" if item.ok else "#8b3136"))
                self.status_table.setItem(row, 1, status_item)
                self.status_table.setItem(row, 2, QTableWidgetItem(item.detail))
            self.status_table.resizeColumnsToContents()
            self.status_table.horizontalHeader().setStretchLastSection(True)
            self.summary.setText('EXTERNAL RUNTIME: READY' if bridge_report.available else 'EXTERNAL RUNTIME: INCOMPLETE')
            self.summary.setStyleSheet(
                "QLabel { color:white; background:%s; padding:8px; font-weight:700; }" % ("#31784b" if bridge_report.available else "#8b3136")
            )
            for warning in bridge_report.warnings:
                self.log.appendPlainText("WARNING: " + warning)
            # External runtimes are read/use-only from this manager. Repair,
            # update and model deletion must never mutate a pre-existing tree.
            self.repair_btn.setEnabled(False)
            self.remove_animate_btn.setEnabled(False)
            self.remove_krea_btn.setEnabled(False)
            self.log.appendPlainText('External runtime: repair/update/removal are disabled to protect the existing installation.')
            return

        self.repair_btn.setEnabled(True)
        self.remove_animate_btn.setEnabled(True)
        self.remove_krea_btn.setEnabled(True)
        try:
            installer = RuntimeInstaller(config)
            report = installer.health_check()
        except Exception as exc:
            self.summary.setText('RUNTIME: ERROR')
            self.log.appendPlainText(str(exc))
            return
        self.status_table.setRowCount(len(report.items))
        for row, item in enumerate(report.items):
            self.status_table.setItem(row, 0, QTableWidgetItem(item.id))
            if item.ok:
                status_text, status_color = "OK", "#31784b"
            elif item.required:
                status_text, status_color = "MISSING", "#8b3136"
            else:
                status_text, status_color = "OPTIONAL", "#78652f"
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor("white"))
            status_item.setBackground(QColor(status_color))
            self.status_table.setItem(row, 1, status_item)
            self.status_table.setItem(row, 2, QTableWidgetItem(item.detail))
        self.status_table.resizeColumnsToContents()
        self.status_table.horizontalHeader().setStretchLastSection(True)
        self.summary.setText("RUNTIME: READY" if report.ready else 'RUNTIME: INCOMPLETE')
        self.summary.setStyleSheet(
            "QLabel { color:white; background:%s; padding:8px; font-weight:700; }" % ("#31784b" if report.ready else "#8b3136")
        )
        if report.ready:
            try:
                python = installer.sync_bridge_configs(validate=True)
                self.log.appendPlainText(f'Bridge synchronized with WanGP environment: {python}')
                self.runtime_config_changed.emit()
            except Exception as exc:
                self.log.appendPlainText(f'Bridge not synchronized: {exc}')

    def _options(self, repair: bool) -> RuntimeInstallOptions:
        return RuntimeInstallOptions(
            install_runtime=self.runtime_check.isChecked(),
            install_wan_animate=self.animate_check.isChecked(),
            install_krea2=self.krea_check.isChecked(),
            accept_anaconda_tos=self.anaconda_tos.isChecked(),
            accept_krea_license=self.krea_license.isChecked(),
            hf_token=self.hf_token_edit.text().strip(),
            repair=repair,
        )

    def start_install(self, repair: bool) -> None:
        if self._thread is not None:
            return
        config = self._current_config()
        config.save()
        preflight = run_runtime_preflight(config)
        if preflight.status == STATUS_BLOCKED:
            QMessageBox.warning(self, 'Installation blocked', 'Preflight is BLOCKED. Fix CUDA, disk space, or paths first.')
            self.log.appendPlainText(preflight.summary())
            return
        options = self._options(repair)
        if options.install_runtime and not options.accept_anaconda_tos:
            QMessageBox.warning(self, "Termini Miniconda", 'Confirm acceptance of the applicable Anaconda/Miniconda terms.')
            return
        if options.install_krea2 and not options.accept_krea_license:
            QMessageBox.warning(self, 'Krea 2 License', 'To install/use Krea 2, confirm the Krea 2 Community License and AUP.')
            return
        self._set_busy(True)
        self.progress.setValue(0)
        self.log.appendPlainText(f'=== Starting installation {APP_VERSION} ===')
        thread = QThread(self)
        worker = RuntimeInstallWorker(config, options)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._thread_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(str, float, str)
    def _on_progress(self, phase: str, fraction: float, message: str) -> None:
        self.progress.setValue(int(max(0.0, min(1.0, fraction)) * 1000))
        self.log.appendPlainText(f"[{phase}] {message}")

    @Slot(object)
    def _on_finished(self, state) -> None:
        self.log.appendPlainText(f'Installation completed: {state.status}')
        self.progress.setValue(1000)
        self.refresh_status()
        self.runtime_config_changed.emit()
        QMessageBox.information(self, 'AI Runtime', 'Installation completed. The Generate/Image Gen bridge has been synchronized with the dedicated WanGP Python 3.11 environment.')

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.log.appendPlainText('ERROR: ' + message)
        QMessageBox.critical(self, 'Runtime Installation Failed', message)

    @Slot()
    def _thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._set_busy(False)

    def cancel_install(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.log.appendPlainText('Cancellation requested: the process will stop at the next safe checkpoint.')

    def remove_model(self, model_id: str) -> None:
        spec = self.manifest.models[model_id]
        answer = QMessageBox.question(self, 'Remove Model', f'Remove {spec.label}? The base runtime will remain installed.')
        if answer != QMessageBox.Yes:
            return
        try:
            removed = RuntimeInstaller(self._current_config()).remove_model(model_id)
        except Exception as exc:
            QMessageBox.critical(self, 'Removal failed', str(exc))
            return
        self.log.appendPlainText(f"{spec.label}: {('removed' if removed else 'not present')}")
        self.refresh_status()
