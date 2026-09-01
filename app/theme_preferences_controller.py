from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QDialog

from app.preferences_dialog import PreferencesDialog
from app.ui_theme import (
    DEFAULT_WORKSTATION_THEME,
    STATUS_BAR_STYLESHEET,
    WORKSTATION_THEMES,
    next_theme_name,
    normalize_theme_name,
    theme_button_stylesheet,
)


class ThemePreferencesController:
    """Own workstation-theme selection, persistence hooks and presentation updates."""

    def __init__(
        self,
        *,
        parent,
        workstation_provider: Callable[[], object | None],
        status_bar_provider: Callable[[], object | None],
        switch_action,
        switch_widget,
        persist_callback: Callable[[], None],
        initial_theme: str = DEFAULT_WORKSTATION_THEME,
    ) -> None:
        self.parent = parent
        self.workstation_provider = workstation_provider
        self.status_bar_provider = status_bar_provider
        self.switch_action = switch_action
        self.switch_widget = switch_widget
        self.persist_callback = persist_callback
        self.theme_name = normalize_theme_name(initial_theme)

    def apply(self, *, persist: bool = True) -> None:
        workstation = self.workstation_provider()
        apply_theme = getattr(workstation, 'apply_theme', None)
        if callable(apply_theme):
            apply_theme(self.theme_name)

        status = self.status_bar_provider()
        if status is not None:
            status.setStyleSheet(STATUS_BAR_STYLESHEET)

        theme = WORKSTATION_THEMES[self.theme_name]
        if self.switch_action is not None:
            self.switch_action.setText(f'Theme: {theme.label}')
        if self.switch_widget is not None:
            self.switch_widget.setStyleSheet(theme_button_stylesheet(self.theme_name))

        if persist:
            self.persist_callback()

    def set_theme(self, theme_name: str, *, persist: bool = True) -> None:
        self.theme_name = normalize_theme_name(theme_name)
        self.apply(persist=persist)

    def cycle(self) -> None:
        self.set_theme(next_theme_name(self.theme_name), persist=True)

    def open_preferences(self) -> None:
        dialog = PreferencesDialog(self.parent, workstation_theme=self.theme_name)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.set_theme(dialog.selected_workstation_theme(), persist=True)

    def snapshot(self) -> dict[str, str]:
        return {'workstation_theme': self.theme_name}

    def restore(self, value: dict | None) -> None:
        if not isinstance(value, dict):
            self.apply(persist=False)
            return
        # ``tab_theme`` is read-only migration support for R5c8/P1-E profiles.
        theme_name = value.get('workstation_theme', value.get('tab_theme', DEFAULT_WORKSTATION_THEME))
        self.set_theme(str(theme_name), persist=False)
