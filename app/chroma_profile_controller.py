from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Any, Callable

from app.models import BackgroundColorRule, ChromaKeySettings
from app.profile_store import ProfilesStore


@contextmanager
def _signals_blocked(widget: Any):
    """Block Qt-like widget signals without importing Qt in this controller module."""
    previous = widget.blockSignals(True)
    try:
        yield widget
    finally:
        widget.blockSignals(previous)


class ChromaProfileController:
    """Owns alpha/chroma profile persistence and UI synchronization.

    The controller intentionally uses duck-typed widgets/callbacks so the persistence
    logic can be tested without importing PySide6. MainWindow remains the orchestration
    hub, while profile lifecycle and serialization live here.
    """

    def __init__(
        self,
        *,
        store: ProfilesStore,
        settings: ChromaKeySettings,
        profile_combo: Any,
        tolerance_slider: Any,
        softness_slider: Any,
        cleanup_slider: Any,
        decontam_slider: Any,
        keying_mode_combo: Any,
        outer_border_checkbox: Any,
        outer_border_spin: Any,
        subject_expand_checkbox: Any,
        subject_expand_spin: Any,
        refresh_rules: Callable[[], None],
        update_swatch: Callable[[], None],
        refresh_previews: Callable[[], None],
        has_current_frame: Callable[[], bool],
        mark_alignment_dirty: Callable[[], None],
        mark_smart_dirty: Callable[[], None],
        sync_cleanup_selection: Callable[[], None],
        ask_profile_name: Callable[[], str | None],
        confirm_delete: Callable[[str], bool],
        show_info: Callable[[str, str], None],
        status: Callable[[str], None],
    ) -> None:
        self.store = store
        self.settings = settings
        self.profile_combo = profile_combo
        self.tolerance_slider = tolerance_slider
        self.softness_slider = softness_slider
        self.cleanup_slider = cleanup_slider
        self.decontam_slider = decontam_slider
        self.keying_mode_combo = keying_mode_combo
        self.outer_border_checkbox = outer_border_checkbox
        self.outer_border_spin = outer_border_spin
        self.subject_expand_checkbox = subject_expand_checkbox
        self.subject_expand_spin = subject_expand_spin
        self.refresh_rules = refresh_rules
        self.update_swatch = update_swatch
        self.refresh_previews = refresh_previews
        self.has_current_frame = has_current_frame
        self.mark_alignment_dirty = mark_alignment_dirty
        self.mark_smart_dirty = mark_smart_dirty
        self.sync_cleanup_selection = sync_cleanup_selection
        self.ask_profile_name = ask_profile_name
        self.confirm_delete = confirm_delete
        self.show_info = show_info
        self.status = status
        self.has_saved_last = self.store.get_last_used('chroma') is not None

    def capture_profile_data(self) -> dict[str, Any]:
        return {
            'background_rgb': list(self.settings.background_rgb),
            'tolerance': int(self.settings.tolerance),
            'softness': int(self.settings.softness),
            'cleanup_radius': int(self.settings.cleanup_radius),
            'edge_decontamination': int(self.settings.edge_decontamination),
            'keying_mode': str(self.settings.keying_mode),
            'additional_background_colors': [rule.to_dict() for rule in self.settings.additional_background_colors],
            'outer_border_mask_px': int(self.settings.outer_border_mask_px),
            'subject_edge_mask_expand_px': int(self.settings.subject_edge_mask_expand_px),
        }

    def apply_profile_data(self, data: dict[str, Any], *, persist_last: bool = True) -> None:
        rgb = data.get('background_rgb', self.settings.background_rgb)
        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
            self.settings.background_rgb = tuple(int(v) for v in rgb)
        self.settings.tolerance = int(data.get('tolerance', self.settings.tolerance))
        self.settings.softness = int(data.get('softness', self.settings.softness))
        self.settings.cleanup_radius = int(data.get('cleanup_radius', self.settings.cleanup_radius))
        self.settings.edge_decontamination = int(data.get('edge_decontamination', self.settings.edge_decontamination))
        self.settings.keying_mode = str(data.get('keying_mode', self.settings.keying_mode))

        parsed_rules: list[BackgroundColorRule] = []
        payload = data.get('additional_background_colors', [])
        if isinstance(payload, list):
            for item in payload[:16]:
                if isinstance(item, dict):
                    try:
                        parsed_rules.append(BackgroundColorRule.from_dict(item))
                    except (TypeError, ValueError):
                        continue
        self.settings.additional_background_colors = parsed_rules
        self.settings.outer_border_mask_px = max(0, int(data.get('outer_border_mask_px', 0)))
        self.settings.subject_edge_mask_expand_px = max(
            0, min(16, int(data.get('subject_edge_mask_expand_px', 0)))
        )

        with ExitStack() as stack:
            for widget in (
                self.tolerance_slider,
                self.softness_slider,
                self.cleanup_slider,
                self.decontam_slider,
                self.keying_mode_combo,
                self.outer_border_checkbox,
                self.outer_border_spin,
                self.subject_expand_checkbox,
                self.subject_expand_spin,
            ):
                stack.enter_context(_signals_blocked(widget))
            self.tolerance_slider.setValue(self.settings.tolerance)
            self.softness_slider.setValue(self.settings.softness)
            self.cleanup_slider.setValue(self.settings.cleanup_radius)
            self.decontam_slider.setValue(self.settings.edge_decontamination)
            mode_index = self.keying_mode_combo.findData(self.settings.keying_mode)
            self.keying_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
            self.outer_border_checkbox.setChecked(self.settings.outer_border_mask_px > 0)
            self.outer_border_spin.setValue(self.settings.outer_border_mask_px if self.settings.outer_border_mask_px > 0 else 8)
            self.outer_border_spin.setEnabled(self.outer_border_checkbox.isChecked())
            self.subject_expand_checkbox.setChecked(self.settings.subject_edge_mask_expand_px > 0)
            self.subject_expand_spin.setValue(
                self.settings.subject_edge_mask_expand_px if self.settings.subject_edge_mask_expand_px > 0 else 2
            )
            self.subject_expand_spin.setEnabled(self.subject_expand_checkbox.isChecked())

        self.update_swatch()
        self.refresh_rules()
        if persist_last:
            self.store.set_last_used('chroma', self.capture_profile_data())
            self.has_saved_last = True
        if self.has_current_frame():
            self.refresh_previews()
        self.mark_alignment_dirty()
        self.mark_smart_dirty()
        self.sync_cleanup_selection()

    def refresh_profiles_combo(self, selected_name: str | None = None) -> None:
        names = self.store.list_profiles('chroma')
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        if selected_name and selected_name in names:
            self.profile_combo.setCurrentText(selected_name)

    def load_last_used(self) -> None:
        data = self.store.get_last_used('chroma')
        if data is not None:
            self.apply_profile_data(data, persist_last=False)
            self.has_saved_last = True

    def remember_current(self) -> None:
        self.store.set_last_used('chroma', self.capture_profile_data())
        self.has_saved_last = True

    def save_current_as(self) -> None:
        name = self.ask_profile_name()
        if name is None:
            return
        normalized = name.strip()
        if not normalized:
            return
        self.store.set_profile('chroma', normalized, self.capture_profile_data())
        self.refresh_profiles_combo(normalized)
        self.status(f'Profilo chroma salvato: {normalized}')

    def load_selected(self) -> None:
        name = self.profile_combo.currentText().strip()
        if not name:
            return
        data = self.store.get_profile('chroma', name)
        if data is None:
            self.show_info('Profilo non trovato', 'Il profilo selezionato non è disponibile.')
            self.refresh_profiles_combo()
            return
        self.apply_profile_data(data, persist_last=True)
        self.status(f'Profilo chroma caricato: {name}')

    def delete_selected(self) -> None:
        name = self.profile_combo.currentText().strip()
        if not name or not self.confirm_delete(name):
            return
        self.store.delete_profile('chroma', name)
        self.refresh_profiles_combo()
        self.status(f'Profilo chroma eliminato: {name}')
