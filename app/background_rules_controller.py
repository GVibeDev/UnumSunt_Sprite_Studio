from __future__ import annotations

from typing import Any, Callable

from app.models import BackgroundColorRule, ChromaKeySettings


class BackgroundRulesController:
    """Owns lifecycle and sampling state for additional background color rules."""

    MAX_RULES = 16

    def __init__(
        self,
        *,
        settings: ChromaKeySettings,
        list_widget: Any,
        has_current_frame: Callable[[], bool],
        choose_color: Callable[[tuple[int, int, int]], tuple[int, int, int] | None],
        ask_tolerance: Callable[[int], int | None],
        show_warning: Callable[[str, str], None],
        show_info: Callable[[str, str], None],
        status: Callable[[str], None],
        changed: Callable[[], None],
    ) -> None:
        self.settings = settings
        self.list_widget = list_widget
        self.has_current_frame = has_current_frame
        self.choose_color = choose_color
        self.ask_tolerance = ask_tolerance
        self.show_warning = show_warning
        self.show_info = show_info
        self.status = status
        self.changed = changed
        self._sample_armed = False

    @property
    def sample_armed(self) -> bool:
        return self._sample_armed

    def refresh_list(self) -> None:
        self.list_widget.clear()
        for index, rule in enumerate(self.settings.additional_background_colors):
            r, g, b = rule.rgb
            tolerance_text = 'global' if rule.tolerance is None else str(rule.tolerance)
            state = '✓' if rule.enabled else '○'
            self.list_widget.addItem(
                f'{state} {index + 1:02d} · #{r:02X}{g:02X}{b:02X} · RGB({r},{g},{b}) · tol {tolerance_text}'
            )

    def selected_index(self) -> int | None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.settings.additional_background_colors):
            return None
        return row

    def _at_capacity(self) -> bool:
        if len(self.settings.additional_background_colors) < self.MAX_RULES:
            return False
        self.show_warning('Color Limit', f'There are already {self.MAX_RULES} additional colors.')
        return True

    def _notify_changed(self) -> None:
        self.refresh_list()
        self.changed()

    def add_via_picker(self) -> None:
        if self._at_capacity():
            return
        rgb = self.choose_color(tuple(self.settings.background_rgb))
        if rgb is None:
            return
        self.settings.additional_background_colors.append(
            BackgroundColorRule(rgb=tuple(int(v) for v in rgb), enabled=True, tolerance=None)
        )
        self._notify_changed()

    def arm_sample(self) -> None:
        if not self.has_current_frame():
            self.show_info('No Frames', 'Open a video before sampling an additional color.')
            return
        if self._at_capacity():
            return
        self._sample_armed = True
        self.status('Additional color sampling is active: click the Original preview.')

    def try_consume_sample(self, rgb: tuple[int, int, int], x: int, y: int) -> bool:
        if not self._sample_armed:
            return False
        self._sample_armed = False
        if self._at_capacity():
            return True
        color = tuple(int(v) for v in rgb)
        self.settings.additional_background_colors.append(
            BackgroundColorRule(rgb=color, enabled=True, tolerance=None)
        )
        self._notify_changed()
        self.status(f'Additional color sampled at ({x}, {y}): RGB {color}')
        return True

    def toggle_selected(self) -> None:
        index = self.selected_index()
        if index is None:
            return
        rule = self.settings.additional_background_colors[index]
        rule.enabled = not rule.enabled
        self._notify_changed()

    def set_selected_tolerance(self) -> None:
        index = self.selected_index()
        if index is None:
            return
        rule = self.settings.additional_background_colors[index]
        current = -1 if rule.tolerance is None else int(rule.tolerance)
        value = self.ask_tolerance(current)
        if value is None:
            return
        rule.tolerance = None if int(value) < 0 else int(value)
        self._notify_changed()

    def remove_selected(self) -> None:
        index = self.selected_index()
        if index is None:
            return
        self.settings.additional_background_colors.pop(index)
        self._notify_changed()

    def clear(self) -> None:
        if not self.settings.additional_background_colors:
            return
        self.settings.additional_background_colors.clear()
        self._notify_changed()
