from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.prompt_builder import (
    ACTIONS,
    BACKGROUNDS,
    CAMERAS,
    CONSTRAINT_KEYS,
    DIRECTIONS,
    IDENTITY_LEVELS,
    MOTIONS,
    OUTPUT_PURPOSES,
    PromptProfileStore,
    background_rgb_for_state,
    build_prompt_profile,
    compose_negative_prompt,
    compose_prompt,
    default_builder_state,
    normalize_prompt_profile,
)
from app.profile_store import ProfilesStore


_CONSTRAINT_LABELS = {
    'preserve_face': 'Preserve face',
    'preserve_hairstyle': 'Preserve hairstyle',
    'preserve_outfit': 'Preserve outfit',
    'preserve_equipment': 'Preserve equipment',
    'preserve_body_proportions': 'Preserve body proportions',
    'keep_full_body_visible': 'Keep full body visible',
    'keep_subject_centered': 'Keep subject centered',
    'no_camera_movement': 'No camera movement',
    'no_scene_change': 'No scene change',
    'no_additional_objects': 'No additional objects',
    'flat_background': 'Flat background',
}


class PromptBuilderWorkspace(QWidget):
    status_message = Signal(str)
    apply_generation_profile_requested = Signal(dict)

    def __init__(
        self,
        *,
        current_generation_profile_provider: Callable[[], dict],
        profiles_store: ProfilesStore | None = None,
    ) -> None:
        super().__init__()
        self.current_generation_profile_provider = current_generation_profile_provider
        self.profiles_store = profiles_store or ProfilesStore()
        self.prompt_store = PromptProfileStore(self.profiles_store)
        self._custom_background_rgb = [0, 255, 0]
        self._build_ui()
        self._refresh_profiles('Default Walk')
        profile = self.prompt_store.get('Default Walk')
        if profile:
            self._apply_profile(profile)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        banner = QLabel(
            'R5e7 — Prompt Builder & Prompt Profiles. Il builder compone prompt strutturati ma il testo finale resta sempre visibile, modificabile e applicato a Genera solo su comando esplicito.'
        )
        banner.setWordWrap(True)
        banner.setStyleSheet('QLabel { color: #f4f6f8; padding: 9px; background: #29263b; border: 1px solid #69609a; }')
        root.addWidget(banner)

        profiles_group = QGroupBox('Prompt Profiles')
        profiles_form = QFormLayout(profiles_group)
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(300)
        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        load_button = QPushButton('Carica')
        load_button.clicked.connect(self._load_selected_profile)
        save_button = QPushButton('Salva come…')
        save_button.clicked.connect(self._save_profile_as)
        delete_button = QPushButton('Elimina')
        delete_button.clicked.connect(self._delete_selected_profile)
        actions_layout.addWidget(load_button)
        actions_layout.addWidget(save_button)
        actions_layout.addWidget(delete_button)
        profiles_form.addRow('Profilo', self.profile_combo)
        profiles_form.addRow('', actions)
        root.addWidget(profiles_group)

        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)

        structure_group = QGroupBox('Prompt Builder')
        form = QFormLayout(structure_group)
        self.action_combo = QComboBox(); self.action_combo.addItems(ACTIONS)
        self.custom_action_edit = QPlainTextEdit(); self.custom_action_edit.setMaximumHeight(62)
        self.direction_combo = QComboBox(); self.direction_combo.addItems(DIRECTIONS)
        self.motion_combo = QComboBox(); self.motion_combo.addItems(MOTIONS)
        self.camera_combo = QComboBox(); self.camera_combo.addItems(CAMERAS)
        self.identity_combo = QComboBox(); self.identity_combo.addItems(IDENTITY_LEVELS)
        self.background_combo = QComboBox(); self.background_combo.addItems(BACKGROUNDS)
        self.output_combo = QComboBox(); self.output_combo.addItems(OUTPUT_PURPOSES)
        self.identity_description_edit = QPlainTextEdit(); self.identity_description_edit.setMaximumHeight(92)
        self.custom_background_button = QPushButton('Scegli RGB custom')
        self.custom_background_button.clicked.connect(self._choose_custom_background)
        self.custom_background_label = QLabel('RGB(0, 255, 0)')
        custom_bg_row = QWidget()
        custom_bg_layout = QHBoxLayout(custom_bg_row); custom_bg_layout.setContentsMargins(0, 0, 0, 0)
        custom_bg_layout.addWidget(self.custom_background_button)
        custom_bg_layout.addWidget(self.custom_background_label, 1)
        form.addRow('Action', self.action_combo)
        form.addRow('Custom action', self.custom_action_edit)
        form.addRow('Direction', self.direction_combo)
        form.addRow('Motion', self.motion_combo)
        form.addRow('Camera', self.camera_combo)
        form.addRow('Identity Preservation', self.identity_combo)
        form.addRow('Background', self.background_combo)
        form.addRow('Custom background', custom_bg_row)
        form.addRow('Output Purpose', self.output_combo)
        form.addRow('Identity / subject', self.identity_description_edit)
        left_layout.addWidget(structure_group)

        constraints_group = QGroupBox('Technical constraints')
        constraints_layout = QVBoxLayout(constraints_group)
        self.constraint_checks: dict[str, QCheckBox] = {}
        for key in CONSTRAINT_KEYS:
            check = QCheckBox(_CONSTRAINT_LABELS[key])
            check.setChecked(True)
            self.constraint_checks[key] = check
            constraints_layout.addWidget(check)
        left_layout.addWidget(constraints_group)
        left_layout.addStretch(1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 0, 0, 0)
        prompts_group = QGroupBox('Prompt finale · sempre modificabile')
        prompts_layout = QVBoxLayout(prompts_group)
        prompts_layout.addWidget(QLabel('Positive prompt'))
        self.positive_edit = QPlainTextEdit()
        self.positive_edit.setMinimumHeight(260)
        prompts_layout.addWidget(self.positive_edit)
        prompts_layout.addWidget(QLabel('Negative prompt'))
        self.negative_edit = QPlainTextEdit()
        self.negative_edit.setMinimumHeight(160)
        prompts_layout.addWidget(self.negative_edit)
        right_layout.addWidget(prompts_group, 1)

        button_row = QHBoxLayout()
        compose_button = QPushButton('Componi dai blocchi')
        compose_button.clicked.connect(self._compose)
        load_generate_button = QPushButton('Carica testo da Genera')
        load_generate_button.clicked.connect(self._load_from_generate)
        apply_button = QPushButton('Applica a Genera')
        apply_button.clicked.connect(self._apply_to_generate)
        button_row.addWidget(compose_button)
        button_row.addWidget(load_generate_button)
        button_row.addWidget(apply_button)
        right_layout.addLayout(button_row)
        note = QLabel(
            '“Componi dai blocchi” rigenera i due campi. Dopo la composizione puoi editarli liberamente. “Applica a Genera” copia il testo corrente: nessun prompt viene sostituito automaticamente.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color: #9198a5;')
        right_layout.addWidget(note)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.action_combo.currentTextChanged.connect(self._update_dynamic_controls)
        self.background_combo.currentTextChanged.connect(self._update_dynamic_controls)
        self._update_dynamic_controls()

    def _current_builder_state(self) -> dict:
        return {
            'action': self.action_combo.currentText(),
            'custom_action': self.custom_action_edit.toPlainText(),
            'direction': self.direction_combo.currentText(),
            'motion': self.motion_combo.currentText(),
            'camera': self.camera_combo.currentText(),
            'identity_preservation': self.identity_combo.currentText(),
            'background': self.background_combo.currentText(),
            'custom_background_rgb': list(self._custom_background_rgb),
            'output_purpose': self.output_combo.currentText(),
            'identity_description': self.identity_description_edit.toPlainText(),
            'constraints': {key: check.isChecked() for key, check in self.constraint_checks.items()},
        }

    def _set_combo_text(self, combo: QComboBox, text: str) -> None:
        index = combo.findText(str(text))
        if index >= 0:
            combo.setCurrentIndex(index)

    def _apply_builder_state(self, state: dict) -> None:
        normalized = build_prompt_profile(name='tmp', builder_state=state)['builder_state']
        self._set_combo_text(self.action_combo, normalized['action'])
        self.custom_action_edit.setPlainText(normalized['custom_action'])
        self._set_combo_text(self.direction_combo, normalized['direction'])
        self._set_combo_text(self.motion_combo, normalized['motion'])
        self._set_combo_text(self.camera_combo, normalized['camera'])
        self._set_combo_text(self.identity_combo, normalized['identity_preservation'])
        self._set_combo_text(self.background_combo, normalized['background'])
        self._set_combo_text(self.output_combo, normalized['output_purpose'])
        self.identity_description_edit.setPlainText(normalized['identity_description'])
        self._custom_background_rgb = list(normalized['custom_background_rgb'])
        self._update_custom_background_label()
        for key, check in self.constraint_checks.items():
            check.setChecked(bool(normalized['constraints'].get(key, False)))
        self._update_dynamic_controls()

    def _compose(self) -> None:
        state = self._current_builder_state()
        self.positive_edit.setPlainText(compose_prompt(state))
        self.negative_edit.setPlainText(compose_negative_prompt(state))
        self.status_message.emit('Prompt composto dai blocchi R5e7. Il testo resta modificabile.')

    def _refresh_profiles(self, selected: str | None = None) -> None:
        names = self.prompt_store.list_names()
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        if selected and selected in names:
            self.profile_combo.setCurrentText(selected)

    def _load_selected_profile(self) -> None:
        name = self.profile_combo.currentText().strip()
        if not name:
            return
        profile = self.prompt_store.get(name)
        if profile is None:
            return
        self._apply_profile(profile)
        self.status_message.emit(f'Prompt profile caricato: {name}')

    def _apply_profile(self, profile: dict) -> None:
        normalized = normalize_prompt_profile(profile)
        self._apply_builder_state(normalized['builder_state'])
        self.positive_edit.setPlainText(normalized['positive_prompt'])
        self.negative_edit.setPlainText(normalized['negative_prompt'])

    def _save_profile_as(self) -> None:
        name, ok = QInputDialog.getText(self, 'Salva Prompt Profile', 'Nome profilo:')
        if not ok:
            return
        normalized_name = name.strip()
        if not normalized_name:
            return
        profile = build_prompt_profile(
            name=normalized_name,
            builder_state=self._current_builder_state(),
            positive_prompt=self.positive_edit.toPlainText(),
            negative_prompt=self.negative_edit.toPlainText(),
            builtin=False,
        )
        self.prompt_store.save(normalized_name, profile)
        self._refresh_profiles(normalized_name)
        self.status_message.emit(f'Prompt profile salvato: {normalized_name}')

    def _delete_selected_profile(self) -> None:
        name = self.profile_combo.currentText().strip()
        if not name:
            return
        try:
            self.prompt_store.delete(name)
        except ValueError as exc:
            QMessageBox.information(self, 'Profilo protetto', str(exc))
            return
        self._refresh_profiles()
        self.status_message.emit(f'Prompt profile eliminato: {name}')

    def _load_from_generate(self) -> None:
        profile = self.current_generation_profile_provider()
        if not isinstance(profile, dict):
            return
        self.positive_edit.setPlainText(str(profile.get('positive_prompt') or ''))
        self.negative_edit.setPlainText(str(profile.get('negative_prompt') or ''))
        metadata = profile.get('prompt_builder_state')
        if isinstance(metadata, dict):
            self._apply_builder_state(metadata)
        rgb = profile.get('requested_background_rgb')
        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
            self._custom_background_rgb = [max(0, min(255, int(v))) for v in rgb]
            self._update_custom_background_label()
        self.status_message.emit('Prompt corrente caricato dal workspace Genera senza ricomposizione automatica.')

    def _apply_to_generate(self) -> None:
        current = deepcopy(self.current_generation_profile_provider())
        state = self._current_builder_state()
        current['positive_prompt'] = self.positive_edit.toPlainText().strip()
        current['negative_prompt'] = self.negative_edit.toPlainText().strip()
        current['requested_background_rgb'] = background_rgb_for_state(state)
        current['prompt_profile_name'] = self.profile_combo.currentText().strip()
        current['prompt_builder_state'] = state
        self.apply_generation_profile_requested.emit(current)
        self.status_message.emit('Prompt R5e7 applicato esplicitamente al workspace Genera.')

    def _choose_custom_background(self) -> None:
        color = QColorDialog.getColor(QColor(*self._custom_background_rgb), self, 'Sfondo custom')
        if not color.isValid():
            return
        self._custom_background_rgb = [color.red(), color.green(), color.blue()]
        self._update_custom_background_label()

    def _update_custom_background_label(self) -> None:
        r, g, b = self._custom_background_rgb
        self.custom_background_label.setText(f'RGB({r}, {g}, {b})')

    def _update_dynamic_controls(self, *_args) -> None:
        self.custom_action_edit.setEnabled(self.action_combo.currentText() == 'Custom')
        enabled = self.background_combo.currentText() == 'Custom'
        self.custom_background_button.setEnabled(enabled)
        self.custom_background_label.setEnabled(enabled)
