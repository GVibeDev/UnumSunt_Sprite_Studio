from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QDialog

from app.preferences_dialog import PreferencesDialog
from app.themed_tab_bar import ThemedTabBar
from app.ui_theme import (
    DEFAULT_TAB_THEME,
    STATUS_BAR_STYLESHEET,
    TAB_THEMES,
    next_theme_name,
    normalize_theme_name,
    theme_button_stylesheet,
)


class ThemePreferencesController:
    """Own UI-theme selection, persistence hooks and presentation updates."""

    def __init__(
        self,
        *,
        parent,
        tab_bar_provider: Callable[[], object | None],
        status_bar_provider: Callable[[], object | None],
        switch_action,
        switch_widget,
        persist_callback: Callable[[], None],
        initial_theme: str = DEFAULT_TAB_THEME,
    ) -> None:
        self.parent = parent
        self.tab_bar_provider = tab_bar_provider
        self.status_bar_provider = status_bar_provider
        self.switch_action = switch_action
        self.switch_widget = switch_widget
        self.persist_callback = persist_callback
        self.theme_name = normalize_theme_name(initial_theme)

    def apply(self, *, persist: bool = True) -> None:
        tab_bar = self.tab_bar_provider()
        if isinstance(tab_bar, ThemedTabBar):
            tab_bar.set_theme(self.theme_name)
            tab_bar.update()

        status = self.status_bar_provider()
        if status is not None:
            status.setStyleSheet(STATUS_BAR_STYLESHEET)

        theme = TAB_THEMES[self.theme_name]
        if self.switch_action is not None:
            self.switch_action.setText(f'Tema: {theme.label}')
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
        dialog = PreferencesDialog(self.parent, tab_theme=self.theme_name)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.set_theme(dialog.selected_tab_theme(), persist=True)

    def snapshot(self) -> dict[str, str]:
        return {'tab_theme': self.theme_name}

    def restore(self, value: dict | None) -> None:
        if not isinstance(value, dict):
            self.apply(persist=False)
            return
        self.set_theme(str(value.get('tab_theme', DEFAULT_TAB_THEME)), persist=False)
