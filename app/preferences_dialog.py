from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from app.ui_theme import TAB_THEMES, THEME_ORDER, normalize_theme_name


class PreferencesDialog(QDialog):
    def __init__(self, parent=None, *, tab_theme: str = 'red') -> None:
        super().__init__(parent)
        self.setWindowTitle('Preferenze')
        self.setModal(True)
        self.resize(430, 180)

        root = QVBoxLayout(self)
        intro = QLabel(
            'Aspetto delle 14 tab principali. Il testo diventa progressivamente più chiaro; '
            'lo sfondo segue il gradiente inverso per conservarne il contrasto.'
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.theme_combo = QComboBox()
        for key in THEME_ORDER:
            self.theme_combo.addItem(TAB_THEMES[key].label, key)
        normalized = normalize_theme_name(tab_theme)
        combo_index = self.theme_combo.findData(normalized)
        self.theme_combo.setCurrentIndex(max(0, combo_index))
        form.addRow('Gradiente tab', self.theme_combo)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_tab_theme(self) -> str:
        return normalize_theme_name(str(self.theme_combo.currentData()))
