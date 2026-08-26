from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.runtime_preflight import (
    GIB,
    STATUS_BLOCKED,
    STATUS_INFO,
    STATUS_READY,
    STATUS_WARNING,
    RuntimePreflightConfig,
    RuntimePreflightReport,
    load_install_plan,
    run_runtime_preflight,
)

from app.version import APP_VERSION

class RuntimePreflightDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f'Local AI Runtime Check · {APP_VERSION}')
        self.resize(980, 700)
        self._report: RuntimePreflightReport | None = None
        self.config = RuntimePreflightConfig.load()
        self.plan = load_install_plan()
        self._build_ui()
        self._populate_plan()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            f'Non-destructive preflight: checks CUDA/driver, disk space, and paths before AI installation. {APP_VERSION} It does NOT enforce minimum thresholds for GPU model, VRAM, or RAM.'
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        paths = QGridLayout()
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
        root.addLayout(paths)

        contract = QLabel(
            f'Current contract: CUDA >= {self.plan.minimum_reported_cuda} · recommended WanGP toolkit {self.plan.recommended_toolkit} · Python {self.plan.python_version} · PyTorch {self.plan.pytorch_version}'
        )
        contract.setWordWrap(True)
        contract.setStyleSheet("QLabel { color: #f4f6f8; background: #242932; padding: 8px; border-radius: 4px; }")
        root.addWidget(contract)

        self.component_table = QTableWidget(0, 6)
        self.component_table.setHorizontalHeaderLabels(['Component', 'Destination', "Download", 'Installed', "Temp", "Type"])
        self.component_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.component_table.verticalHeader().setVisible(False)
        self.component_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.component_table, 2)

        self.summary_label = QLabel('PRE-FLIGHT NOT RUN')
        self.summary_label.setAlignment(Qt.AlignCenter)
        self.summary_label.setStyleSheet("QLabel { color: white; background: #343a46; padding: 10px; font-weight: 700; }")
        root.addWidget(self.summary_label)

        self.check_table = QTableWidget(0, 3)
        self.check_table.setHorizontalHeaderLabels(['Status', 'Check', "Details"])
        self.check_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.check_table.verticalHeader().setVisible(False)
        self.check_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.check_table, 4)

        buttons = QHBoxLayout()
        run_btn = QPushButton('Run Check')
        run_btn.clicked.connect(self.run_check)
        buttons.addWidget(run_btn)
        self.save_btn = QPushButton('Save JSON Report…')
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_report)
        buttons.addWidget(self.save_btn)
        buttons.addStretch(1)
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def _populate_plan(self) -> None:
        self.component_table.setRowCount(len(self.plan.components))
        for row, component in enumerate(self.plan.components):
            values = [
                component.label,
                component.destination,
                f"{component.download_gib:.1f} GiB",
                f"{component.installed_gib:.1f} GiB",
                f"{component.temporary_gib:.1f} GiB",
                "STIMA" if component.estimate else 'CONFIRMED',
            ]
            for column, value in enumerate(values):
                self.component_table.setItem(row, column, QTableWidgetItem(value))
        self.component_table.resizeColumnsToContents()

    def _browse(self, edit: QLineEdit) -> None:
        initial = edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, 'Select Folder', initial)
        if selected:
            edit.setText(selected)

    @staticmethod
    def _status_color(status: str) -> QColor:
        if status == STATUS_READY:
            return QColor(49, 120, 75)
        if status == STATUS_WARNING:
            return QColor(151, 111, 31)
        if status == STATUS_BLOCKED:
            return QColor(139, 49, 54)
        return QColor(65, 73, 88)

    def run_check(self) -> None:
        config = RuntimePreflightConfig(
            runtime_root=self.runtime_edit.text().strip(),
            model_root=self.models_edit.text().strip(),
        )
        try:
            report = run_runtime_preflight(config, plan=self.plan)
        except Exception as exc:
            QMessageBox.critical(self, "Preflight failed", str(exc))
            return
        config.save()
        self.config = config
        self._report = report
        self.save_btn.setEnabled(True)
        self.summary_label.setText(f"LOCAL AI RUNTIME: {report.status}")
        self.summary_label.setStyleSheet(
            f"QLabel {{ color: white; background: {self._status_color(report.status).name()}; padding: 10px; font-weight: 700; }}"
        )
        self.check_table.setRowCount(len(report.checks))
        for row, check in enumerate(report.checks):
            status_item = QTableWidgetItem(check.status)
            status_item.setForeground(QColor("white"))
            status_item.setBackground(self._status_color(check.status))
            self.check_table.setItem(row, 0, status_item)
            self.check_table.setItem(row, 1, QTableWidgetItem(check.label))
            self.check_table.setItem(row, 2, QTableWidgetItem(check.detail))
        self.check_table.resizeColumnsToContents()
        self.check_table.horizontalHeader().setStretchLastSection(True)

    def save_report(self) -> None:
        if self._report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            'Save Preflight Report',
            str(Path.home() / f"unum_sunt_runtime_preflight_{APP_VERSION}.json"),
            "JSON (*.json)",
        )
        if not path:
            return
        self._report.save(path)
