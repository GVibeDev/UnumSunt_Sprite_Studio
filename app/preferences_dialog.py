from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from app.ui_theme import WORKSTATION_THEMES, THEME_ORDER, normalize_theme_name


class PreferencesDialog(QDialog):
    def __init__(self, parent=None, *, workstation_theme: str = 'red') -> None:
        super().__init__(parent)
        self.setWindowTitle('Preferences')
        self.setModal(True)
        self.resize(430, 180)

        root = QVBoxLayout(self)
        intro = QLabel(
            'Choose the accent used by the GENERATE / CREATE / MANAGE workstation navigation, contextual route controls and application chrome.'
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.theme_combo = QComboBox()
        for key in THEME_ORDER:
            self.theme_combo.addItem(WORKSTATION_THEMES[key].label, key)
        normalized = normalize_theme_name(workstation_theme)
        combo_index = self.theme_combo.findData(normalized)
        self.theme_combo.setCurrentIndex(max(0, combo_index))
        form.addRow('Workstation accent', self.theme_combo)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_workstation_theme(self) -> str:
        return normalize_theme_name(str(self.theme_combo.currentData()))
