from __future__ import annotations

from pathlib import Path
import json
import shutil
import numpy as np
from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.alignment_studio import AlignmentStudio
from app.calibration_workspace import CalibrationWorkspace
from app.background_rules_controller import BackgroundRulesController
from app.chroma_profile_controller import ChromaProfileController
from app.character_set_workspace import CharacterSetWorkspace
from app.cleanup_studio import CleanupStudio
from app.chroma_key import (
    EmptySubjectError,
    analyze_background,
    apply_chroma_key,
    apply_chroma_key_with_diagnostics,
    auto_detect_background_rgb,
    create_alpha_mask_with_diagnostics,
    render_checkerboard,
)
from app.export_service import ExportError, export_selected_frames
from app.export_studio import ExportStudio
from app.generation_workspace import GenerationWorkspace
from app.image_generation_workspace import ImageGenerationWorkspace
from app.models import ChromaKeySettings, ExportSettings
from app.preview_label import PreviewLabel
from app.profile_store import ProfilesStore
from app.production_presets import merge_preset_into_pipeline
from app.production_presets_workspace import ProductionPresetsWorkspace
from app.performance_probe import perf_instrument
from app.prompt_builder_workspace import PromptBuilderWorkspace
from app.project_workspace import ProjectWorkspace
from app.smart_selection_studio import SmartSelectionStudio
from app.spritesheet_workspace import SpriteSheetWorkspace
from app.video_source import VideoOpenError, VideoSource
from app.workflow_workspace import WorkflowWorkspace
from app.workflows import WORKFLOW_DEFINITIONS, normalize_workflow_state
from app.ui_commands import TAB_ROUTES, TAB_SHORT_LABELS, TAB_TOOLTIPS, toolbar_command_state
from app.themed_tab_bar import ThemedTabBar
from app.ui_theme import DEFAULT_TAB_THEME
from app.version import APP_VERSION
from app.theme_preferences_controller import ThemePreferencesController
from app.runtime_preflight_dialog import RuntimePreflightDialog
from app.runtime_bridge_controller import RuntimeBridgeController
from app.help_dialog import HelpDialog
from app.version import APP_TITLE


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1560, 960)
        self.video = VideoSource()
        self.profile_store = ProfilesStore()
        self.current_project_path: str | None = None
        self._generation_job_groups: dict[str, str | None] = {}
        self.current_frame_index = 0
        self.current_frame_rgb: np.ndarray | None = None
        self.selected_frames: list[int] = []
        self.chroma_settings = ChromaKeySettings()
        self.rgba_overrides: dict[int, np.ndarray] = {}
        self.background_diagnostic = None
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance_playback)
        self.preview_debounce = QTimer(self)
        self.preview_debounce.setSingleShot(True)
        self.preview_debounce.timeout.connect(self._refresh_previews)
        self._build_ui()
        self.runtime_bridge = RuntimeBridgeController(self)
        self.runtime_bridge.sync_installed_fast()
        self._init_domain_controllers()
        self._set_video_controls_enabled(False)
        self.setStatusBar(QStatusBar(self))
        self.theme_preferences = ThemePreferencesController(
            parent=self,
            tab_bar_provider=lambda: self.workspace_tabs.tabBar() if hasattr(self, 'workspace_tabs') else None,
            status_bar_provider=self.statusBar,
            switch_action=getattr(self, 'theme_switch_action', None),
            switch_widget=getattr(self, 'theme_switch_widget', None),
            persist_callback=self._persist_application_state,
            initial_theme=DEFAULT_TAB_THEME,
        )
        self.theme_preferences.apply(persist=False)
        self.background_rules.refresh_list()
        self.chroma_profiles.refresh_profiles_combo()
        self.chroma_profiles.load_last_used()
        self._restore_app_state()
        if self.statusBar() is not None and not self.statusBar().currentMessage():
            self.statusBar().showMessage('Ready. Create/open a project, or choose Help → Quick Start for the production workflow.')

    def _init_domain_controllers(self) -> None:
        def choose_additional_color(initial_rgb: tuple[int, int, int]) -> tuple[int, int, int] | None:
            color = QColorDialog.getColor(QColor(*initial_rgb), self, 'Additional Background Color')
            if not color.isValid():
                return None
            return color.red(), color.green(), color.blue()

        def ask_additional_tolerance(current: int) -> int | None:
            value, ok = QInputDialog.getInt(
                self,
                'Additional Color Tolerance',
                'Value (-1 = use global tolerance):',
                current,
                -1,
                255,
                1,
            )
            return int(value) if ok else None

        def background_rules_changed() -> None:
            self.chroma_profiles.remember_current()
            self._refresh_previews()
            self.alignment_studio.mark_dirty()
            self.smart_studio.mark_dirty()
            self.cleanup_studio.set_selected_frames(self.selected_frames)

        self.background_rules = BackgroundRulesController(
            settings=self.chroma_settings,
            list_widget=self.additional_colors_list,
            has_current_frame=lambda: self.current_frame_rgb is not None,
            choose_color=choose_additional_color,
            ask_tolerance=ask_additional_tolerance,
            show_warning=lambda title, text: QMessageBox.warning(self, title, text),
            show_info=lambda title, text: QMessageBox.information(self, title, text),
            status=lambda text: self.statusBar().showMessage(text),
            changed=background_rules_changed,
        )

        def ask_profile_name() -> str | None:
            name, ok = QInputDialog.getText(self, 'Save Alpha/Chroma Profile', 'Profile name:')
            return str(name) if ok else None

        self.chroma_profiles = ChromaProfileController(
            store=self.profile_store,
            settings=self.chroma_settings,
            profile_combo=self.chroma_profile_combo,
            tolerance_slider=self.tolerance_slider,
            softness_slider=self.softness_slider,
            cleanup_slider=self.cleanup_slider,
            decontam_slider=self.decontam_slider,
            keying_mode_combo=self.keying_mode_combo,
            outer_border_checkbox=self.outer_border_checkbox,
            outer_border_spin=self.outer_border_spin,
            subject_expand_checkbox=self.subject_expand_checkbox,
            subject_expand_spin=self.subject_expand_spin,
            refresh_rules=self.background_rules.refresh_list,
            update_swatch=self._update_color_swatch,
            refresh_previews=self._refresh_previews,
            has_current_frame=lambda: self.current_frame_rgb is not None,
            mark_alignment_dirty=lambda: self.alignment_studio.mark_dirty(),
            mark_smart_dirty=lambda: self.smart_studio.mark_dirty(),
            sync_cleanup_selection=lambda: self.cleanup_studio.set_selected_frames(self.selected_frames),
            ask_profile_name=ask_profile_name,
            confirm_delete=lambda name: QMessageBox.question(
                self, 'Delete Profile', f'Delete profile "{name}"?'
            ) == QMessageBox.StandardButton.Yes,
            show_info=lambda title, text: QMessageBox.information(self, title, text),
            status=lambda text: self.statusBar().showMessage(text),
        )

    def _build_ui(self) -> None:
        self._build_toolbar()
        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setTabBar(ThemedTabBar(self.workspace_tabs, theme_name=DEFAULT_TAB_THEME))

        self.project_workspace = ProjectWorkspace()
        self.project_workspace.project_changed.connect(self._on_project_changed)
        self.project_workspace.save_requested.connect(self._save_project_snapshot)
        self.project_workspace.active_group_will_change.connect(self._on_active_group_will_change)
        self.project_workspace.active_group_changed.connect(self._on_active_group_changed)
        self.project_workspace.status_message.connect(self.statusBarMessage)
        self.workspace_tabs.addTab(self.project_workspace, '0 · Project')

        self.generation_workspace = GenerationWorkspace()
        self.generation_workspace.video_ready.connect(self._import_generated_video)
        self.generation_workspace.job_started.connect(self._on_generation_job_started)
        self.generation_workspace.job_finished.connect(self._on_generation_job_finished)
        self.generation_workspace.status_message.connect(self.statusBarMessage)
        self.workspace_tabs.addTab(self.generation_workspace, '1 · Generate')

        self.workspace_tabs.addTab(self._build_extraction_workspace(), '2 · R1 Extraction')

        self.cleanup_studio = CleanupStudio(
            frame_loader=self.video.get_frame_rgb,
            metadata_provider=self._get_metadata_or_none,
            chroma_provider=lambda: self.chroma_settings,
            override_getter=self.get_rgba_override,
            override_setter=self.set_rgba_override,
        )
        self.cleanup_studio.frame_requested.connect(self._set_frame)
        self.cleanup_studio.status_message.connect(self.statusBarMessage)
        self.cleanup_studio.overrides_changed.connect(self._on_overrides_changed)
        self.workspace_tabs.addTab(self.cleanup_studio, '3 · Clean-up R5e5-D')

        self.alignment_studio = AlignmentStudio(
            frame_loader=self.video.get_frame_rgb,
            metadata_provider=self._get_metadata_or_none,
            chroma_provider=lambda: self.chroma_settings,
            rgba_override_provider=self.get_rgba_override,
        )
        self.alignment_studio.frame_requested.connect(self._set_frame)
        self.alignment_studio.status_message.connect(self.statusBarMessage)
        self.workspace_tabs.addTab(self.alignment_studio, '4 · Alignment R5e2')

        self.smart_studio = SmartSelectionStudio(
            frame_loader=self.video.get_frame_rgb,
            metadata_provider=self._get_metadata_or_none,
            chroma_provider=lambda: self.chroma_settings,
            current_frame_provider=lambda: self.current_frame_index,
            rgba_override_provider=self.get_rgba_override,
        )
        self.smart_studio.frame_requested.connect(self._set_frame)
        self.smart_studio.selection_applied.connect(self._apply_smart_selection)
        self.smart_studio.status_message.connect(self.statusBarMessage)
        self.workspace_tabs.addTab(self.smart_studio, '5 · Smart Selection R3')

        self.export_studio = ExportStudio(
            raw_frames_provider=self._build_raw_export_payload,
            aligned_frames_provider=self._build_aligned_export_payload,
        )
        self.export_studio.export_completed.connect(self._on_export_completed)
        self.export_studio.status_message.connect(self.statusBarMessage)
        self.workspace_tabs.addTab(self.export_studio, '6 · Export Studio R5e4')

        self.production_presets_workspace = ProductionPresetsWorkspace(
            active_group_provider=self._active_group_context,
            pipeline_provider=self._current_pipeline_for_preset,
            apply_callback=self._apply_production_preset,
        )
        self.production_presets_workspace.status_message.connect(self.statusBarMessage)
        self.workspace_tabs.addTab(self.production_presets_workspace, '7 · Production Presets R5e4a')

        self.calibration_workspace = CalibrationWorkspace(
            project_store_provider=lambda: self.project_workspace.project_store,
            active_group_id_provider=lambda: self.project_workspace.active_group_id,
            current_generation_profile_provider=self.generation_workspace.capture_generation_profile,
        )
        self.calibration_workspace.status_message.connect(self.statusBarMessage)
        self.calibration_workspace.load_generation_profile_requested.connect(self._load_calibration_profile_in_generate)
        self.workspace_tabs.addTab(self.calibration_workspace, '8 · Calibration Lab R5e6')

        self.prompt_builder_workspace = PromptBuilderWorkspace(
            current_generation_profile_provider=self.generation_workspace.capture_generation_profile,
            profiles_store=self.profile_store,
        )
        self.prompt_builder_workspace.status_message.connect(self.statusBarMessage)
        self.prompt_builder_workspace.apply_generation_profile_requested.connect(self._load_prompt_profile_in_generate)
        self.workspace_tabs.addTab(self.prompt_builder_workspace, '9 · Prompt Builder R5e7')

        self.spritesheet_workspace = SpriteSheetWorkspace(
            project_store_provider=lambda: self.project_workspace.project_store,
            active_group_id_provider=lambda: self.project_workspace.active_group_id,
        )
        self.spritesheet_workspace.status_message.connect(self.statusBarMessage)
        self.spritesheet_workspace.sequence_ready.connect(self._import_spritesheet_sequence)
        self.spritesheet_workspace.reference_sheet_ready.connect(self._use_reference_sheet_in_generate)
        self.workspace_tabs.addTab(self.spritesheet_workspace, '10 · Sprite Sheet R5e8')

        self.image_generation_workspace = ImageGenerationWorkspace()
        self.image_generation_workspace.status_message.connect(self.statusBarMessage)
        self.image_generation_workspace.image_ready.connect(self._use_generated_image_as_reference)
        self.image_generation_workspace.job_finished.connect(self._on_image_generation_job_finished)
        self.workspace_tabs.addTab(self.image_generation_workspace, '11 · Image Generator R5e9')

        self.workflow_workspace = WorkflowWorkspace(
            project_store_provider=lambda: self.project_workspace.project_store,
            active_group_id_provider=lambda: self.project_workspace.active_group_id,
        )
        self.workflow_workspace.status_message.connect(self.statusBarMessage)
        self.workflow_workspace.route_requested.connect(self._route_workflow_step)
        self.workflow_workspace.guided_tabs_changed.connect(self._apply_guided_workflow_tabs)
        self.workflow_workspace.settings_checkpoint_requested.connect(self._save_workflow_settings_checkpoint)
        self.workflow_workspace.motion_reference_requested.connect(self._promote_current_video_to_motion_reference)
        self.workspace_tabs.addTab(self.workflow_workspace, '12 · Workflow R5e10')

        self.character_set_workspace = CharacterSetWorkspace(
            project_store_provider=lambda: self.project_workspace.project_store,
            active_group_id_provider=lambda: self.project_workspace.active_group_id,
        )
        self.character_set_workspace.status_message.connect(self.statusBarMessage)
        self.character_set_workspace.activate_group_requested.connect(self.project_workspace.activate_group)
        self.workspace_tabs.addTab(self.character_set_workspace, '13 · Character Set R5e11')

        self._workflow_tab_routes = {
            'project': 0, 'generation': 1, 'extraction': 2, 'cleanup': 3, 'alignment': 4,
            'smart_selection': 5, 'export': 6, 'production_presets': 7, 'calibration': 8,
            'prompt_builder': 9, 'spritesheet': 10, 'image_generation': 11, 'workflow': 12,
            'character_set': 13,
        }
        self.workspace_tabs.currentChanged.connect(self._on_workspace_changed)
        self._apply_workspace_tab_style()
        self.setCentralWidget(self.workspace_tabs)
        self._refresh_command_context()

    def get_rgba_override(self, frame_index: int) -> np.ndarray | None:
        value = self.rgba_overrides.get(int(frame_index))
        if value is not None:
            return value.copy()
        # Transparent spritesheet imports already contain a valid alpha mask. Preserve it
        # as the non-destructive base layer instead of forcing a second chroma pass.
        if self.video.is_open and self.video.source_kind == 'sequence':
            try:
                rgba = self.video.get_frame_rgba(int(frame_index))
            except Exception:
                return None
            if np.any(rgba[:, :, 3] < 255):
                return rgba.copy()
        return None

    def set_rgba_override(self, frame_index: int, rgba: np.ndarray | None) -> None:
        if rgba is None:
            self.rgba_overrides.pop(int(frame_index), None)
        else:
            self.rgba_overrides[int(frame_index)] = rgba.copy()

    def _on_overrides_changed(self) -> None:
        self.alignment_studio.mark_dirty('Retouched subject masks changed. Update R2 before exporting.')
        self.smart_studio.mark_dirty('Clean-up changed: repeat the R3 analysis if needed.')
        self._refresh_previews()

    def statusBarMessage(self, message: str) -> None:
        if self.statusBar() is not None:
            self.statusBar().showMessage(message)

    def _get_metadata_or_none(self):
        return self.video.metadata if self.video.is_open else None

    def _build_extraction_workspace(self) -> QWidget:
        page = QWidget()
        root_layout = QVBoxLayout(page)
        root_layout.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.preview_tabs = QTabWidget()
        self.original_preview = PreviewLabel(clickable=True)
        self.mask_preview = PreviewLabel()
        self.result_preview = PreviewLabel()
        self.subject_preview = PreviewLabel()
        self.background_candidate_preview = PreviewLabel()
        self.original_preview.image_clicked.connect(self._sample_background_from_frame)
        self.preview_tabs.addTab(self.original_preview, 'Original')
        self.preview_tabs.addTab(self.mask_preview, 'Mask')
        self.preview_tabs.addTab(self.result_preview, 'Transparent Result')
        self.preview_tabs.addTab(self.subject_preview, 'Detected Subject')
        self.preview_tabs.addTab(self.background_candidate_preview, 'Background candidate')
        splitter.addWidget(self.preview_tabs)
        side_panel = self._build_side_panel()
        side_scroll = QScrollArea()
        side_scroll.setWidget(side_panel)
        side_scroll.setWidgetResizable(True)
        side_scroll.setMinimumWidth(430)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        splitter.addWidget(side_scroll)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1040, 460])
        root_layout.addWidget(splitter, 1)
        root_layout.addWidget(self._build_timeline())
        return page

    def _build_toolbar(self) -> None:
        """Build the R5e13b traditional menu and one contextual command toolbar."""
        self._video_controls_available = False
        self._toolbar_command_widgets: dict[str, QWidget] = {}
        self._toolbar_command_actions: dict[str, QAction] = {}

        def action(command_id: str, label: str, callback, shortcut: QKeySequence | str | None = None) -> QAction:
            item = QAction(label, self)
            if shortcut is not None:
                item.setShortcut(shortcut if isinstance(shortcut, QKeySequence) else QKeySequence(shortcut))
            item.triggered.connect(callback)
            item.setProperty('command_id', command_id)
            return item

        self.new_project_action = action('new_project', 'New Project', lambda: self.project_workspace._create_project_interactive(), QKeySequence.StandardKey.New)
        self.open_project_action = action('open_project', 'Open Project…', lambda: self.project_workspace._open_project_interactive(), QKeySequence.StandardKey.Open)
        self.save_project_action = action('save_project', 'Save Project', self._save_project_snapshot, QKeySequence.StandardKey.Save)
        self.open_video_action = action('open_video', 'Open Video…', self._open_video, 'Ctrl+Shift+O')
        self.open_spritesheet_action = action('open_spritesheet', 'Open Spritesheet…', self._open_spritesheet_from_command, 'Ctrl+Alt+O')

        self.play_action = action('play', 'Play', self._toggle_playback, QKeySequence(Qt.Key.Key_Space))
        self.prev_action = action('prev_frame', 'Frame −1', lambda: self._set_frame(self.current_frame_index - 1), QKeySequence(Qt.Key.Key_Left))
        self.next_action = action('next_frame', 'Frame +1', lambda: self._set_frame(self.current_frame_index + 1), QKeySequence(Qt.Key.Key_Right))
        self.add_frame_action = action('add_frame', 'Add Frame', self._add_current_frame, 'A')
        self.remove_frame_action = action('remove_frame', 'Remove Selected', self._remove_selected_frames, QKeySequence.StandardKey.Delete)
        self.export_action = action('export_r1', 'Export R1 Selection…', self._export_frames, 'Ctrl+Shift+E')

        self.route_project_action = action('route_project', 'Project / Project Groups', lambda: self._route_command_workspace('project'))
        self.route_generation_action = action('route_generation', 'Video Generation', lambda: self._route_command_workspace('generation'))
        self.route_cleanup_action = action('route_cleanup', 'Clean-up / Alpha', lambda: self._route_command_workspace('cleanup'))
        self.route_export_action = action('route_export', 'Export Studio', lambda: self._route_command_workspace('export'))
        self.route_presets_action = action('route_presets', 'Production Presets', lambda: self._route_command_workspace('production_presets'))
        self.route_calibration_action = action('route_calibration', 'Calibration Lab', lambda: self._route_command_workspace('calibration'))
        self.route_prompt_action = action('route_prompt', 'Prompt Builder', lambda: self._route_command_workspace('prompt_builder'))
        self.route_spritesheet_action = action('route_spritesheet', 'Sprite Sheet workspace', lambda: self._route_command_workspace('spritesheet'))
        self.route_image_action = action('route_image', 'Image Generator', lambda: self._route_command_workspace('image_generation'))
        self.route_workflow_action = action('route_workflow', 'Workflow Router', lambda: self._route_command_workspace('workflow'))
        self.route_character_action = action('route_character', 'Character Set / Layer Manager', lambda: self._route_command_workspace('character_set'))
        self.checkpoint_action = action('checkpoint', 'Save Settings Checkpoint', self._save_workflow_settings_checkpoint)
        quit_action = action('quit', 'Exit', self.close, QKeySequence.StandardKey.Quit)

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('File')
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.save_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.open_video_action)
        file_menu.addAction(self.open_spritesheet_action)
        file_menu.addSeparator()
        self.preferences_action = action('preferences', 'Preferences…', lambda: self.theme_preferences.open_preferences())
        file_menu.addAction(self.preferences_action)
        self.runtime_preflight_action = action('runtime_preflight', 'Check AI Runtime…', lambda: RuntimePreflightDialog(self).exec())
        file_menu.addAction(self.runtime_preflight_action)
        self.runtime_manager_action = action('runtime_manager', 'AI Runtime Manager…', lambda: self.runtime_bridge.open_manager())
        file_menu.addAction(self.runtime_manager_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        edit_menu = menu_bar.addMenu('Edit')
        edit_menu.addAction(self.add_frame_action)
        edit_menu.addAction(self.remove_frame_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.route_cleanup_action)

        project_menu = menu_bar.addMenu('Project')
        project_menu.addAction(self.route_project_action)
        project_menu.addAction(self.route_workflow_action)
        project_menu.addAction(self.route_character_action)
        project_menu.addSeparator()
        project_menu.addAction(self.checkpoint_action)

        image_menu = menu_bar.addMenu('Image')
        image_menu.addAction(self.route_image_action)
        image_menu.addAction(self.route_prompt_action)
        image_menu.addAction(self.route_cleanup_action)

        video_menu = menu_bar.addMenu('Video')
        video_menu.addAction(self.open_video_action)
        video_menu.addAction(self.route_generation_action)
        video_menu.addSeparator()
        video_menu.addAction(self.play_action)
        video_menu.addAction(self.prev_action)
        video_menu.addAction(self.next_action)
        video_menu.addSeparator()
        video_menu.addAction(self.route_calibration_action)

        spritesheet_menu = menu_bar.addMenu('Spritesheet')
        spritesheet_menu.addAction(self.open_spritesheet_action)
        spritesheet_menu.addAction(self.route_spritesheet_action)
        spritesheet_menu.addAction(self.route_character_action)

        presets_menu = menu_bar.addMenu('Preset')
        presets_menu.addAction(self.route_presets_action)
        presets_menu.addAction(self.route_prompt_action)
        presets_menu.addAction(self.route_calibration_action)

        export_menu = menu_bar.addMenu('Export')
        export_menu.addAction(self.export_action)
        export_menu.addAction(self.route_export_action)

        help_menu = menu_bar.addMenu('Help')
        self.quick_start_action = action(
            'help_quick_start',
            'Quick Start…',
            lambda: self._open_help('Quick Start'),
            QKeySequence.StandardKey.HelpContents,
        )
        self.production_guide_action = action(
            'help_production',
            'Production Workflow…',
            lambda: self._open_help('Production Workflow'),
        )
        self.local_ai_guide_action = action(
            'help_local_ai',
            'Local AI Setup…',
            lambda: self._open_help('Local AI'),
        )
        self.about_legal_action = action(
            'help_legal',
            'About & Licensing…',
            lambda: self._open_help('About & Licensing'),
        )
        help_menu.addAction(self.quick_start_action)
        help_menu.addAction(self.production_guide_action)
        help_menu.addAction(self.local_ai_guide_action)
        help_menu.addSeparator()
        help_menu.addAction(self.about_legal_action)

        toolbar = QToolBar('Context Commands')
        toolbar.setMovable(False)
        toolbar.setObjectName('contextual-command-toolbar')
        self.command_toolbar = toolbar
        self.addToolBar(toolbar)
        for command_id, item in (
            ('new_project', self.new_project_action),
            ('save_project', self.save_project_action),
            ('open_video', self.open_video_action),
            ('open_spritesheet', self.open_spritesheet_action),
            ('play', self.play_action),
            ('prev_frame', self.prev_action),
            ('next_frame', self.next_action),
            ('add_frame', self.add_frame_action),
            ('remove_frame', self.remove_frame_action),
            ('export_r1', self.export_action),
        ):
            toolbar.addAction(item)
            self._toolbar_command_actions[command_id] = item
        toolbar.addSeparator()
        self.command_context_label = QLabel('Context: —')
        self.command_context_label.setStyleSheet('QLabel { padding: 4px 8px; color: #aeb8c7; }')
        toolbar.addWidget(self.command_context_label)
        toolbar.addSeparator()
        self.theme_switch_action = QAction('Theme: —', self)
        self.theme_switch_action.setToolTip('Quickly cycle the tab gradient: Red → Green → Blue')
        self.theme_switch_action.triggered.connect(lambda: self.theme_preferences.cycle())
        toolbar.addAction(self.theme_switch_action)
        self.theme_switch_widget = toolbar.widgetForAction(self.theme_switch_action)

    def _open_help(self, section: str = 'Quick Start') -> None:
        dialog = HelpDialog(self, section=section)
        dialog.exec()

    def _current_workspace_route(self) -> str:
        if not hasattr(self, 'workspace_tabs'):
            return 'project'
        index = self.workspace_tabs.currentIndex()
        if 0 <= index < len(TAB_ROUTES):
            return TAB_ROUTES[index]
        return 'project'

    def _refresh_command_context(self) -> None:
        if not hasattr(self, '_toolbar_command_actions'):
            return
        context = self._current_workspace_route()
        video_open = bool(getattr(self, '_video_controls_available', False))
        for command_id, item in self._toolbar_command_actions.items():
            visible, enabled = toolbar_command_state(command_id, context, video_open=video_open)
            item.setEnabled(enabled if visible else item.isEnabled())
            widget = self.command_toolbar.widgetForAction(item) if hasattr(self, 'command_toolbar') else None
            if widget is not None:
                widget.setVisible(visible)
            # Contextual editing/playback shortcuts must be disabled outside their
            # workspace too, otherwise hidden toolbar commands would still fire.
            if command_id in {'play', 'prev_frame', 'next_frame', 'add_frame', 'remove_frame', 'export_r1'}:
                item.setEnabled(enabled)
            elif command_id in {'new_project', 'save_project', 'open_video', 'open_spritesheet'}:
                item.setEnabled(True)
        if hasattr(self, 'command_context_label'):
            label = TAB_SHORT_LABELS[TAB_ROUTES.index(context)] if context in TAB_ROUTES else context
            self.command_context_label.setText(f'Context: {label}')

    def _apply_workspace_tab_style(self) -> None:
        if not hasattr(self, 'workspace_tabs'):
            return
        self.workspace_tabs.setUsesScrollButtons(True)
        self.workspace_tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.workspace_tabs.setDocumentMode(True)
        tab_bar = self.workspace_tabs.tabBar()
        if isinstance(tab_bar, ThemedTabBar):
            tab_bar.set_theme(self.theme_preferences.theme_name if hasattr(self, 'theme_preferences') else DEFAULT_TAB_THEME)
        for index in range(min(self.workspace_tabs.count(), len(TAB_SHORT_LABELS))):
            self.workspace_tabs.setTabText(index, TAB_SHORT_LABELS[index])
            self.workspace_tabs.setTabToolTip(index, TAB_TOOLTIPS[index])
        self.workspace_tabs.setStyleSheet('QTabWidget::pane { border-top: 1px solid #353b44; }')

    def _route_command_workspace(self, route: str) -> None:
        index = getattr(self, '_workflow_tab_routes', {}).get(str(route))
        if index is None:
            return
        # An explicit menu command is allowed to reveal a tab hidden by Guided View.
        self.workspace_tabs.setTabVisible(index, True)
        self.workspace_tabs.setCurrentIndex(index)

    def _open_spritesheet_from_command(self) -> None:
        self._route_command_workspace('spritesheet')
        if hasattr(self, 'spritesheet_workspace'):
            self.spritesheet_workspace._open_sheet()

    def _build_side_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(400)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)

        info_group = QGroupBox('Video')
        info_layout = QFormLayout(info_group)
        self.file_label = QLabel('—')
        self.file_label.setWordWrap(True)
        self.video_size_label = QLabel('—')
        self.video_fps_label = QLabel('—')
        self.video_frames_label = QLabel('—')
        self.video_duration_label = QLabel('—')
        info_layout.addRow('File', self.file_label)
        info_layout.addRow('Resolution', self.video_size_label)
        info_layout.addRow('FPS', self.video_fps_label)
        info_layout.addRow('Frames', self.video_frames_label)
        info_layout.addRow('Duration', self.video_duration_label)
        layout.addWidget(info_group)

        key_group = QGroupBox('Background Extraction')
        key_layout = QVBoxLayout(key_group)
        color_row = QHBoxLayout()
        self.color_button = QPushButton('Choose Color')
        self.color_button.clicked.connect(self._choose_background_color)
        self.auto_color_button = QPushButton('Detect Corners')
        self.auto_color_button.clicked.connect(self._auto_detect_background)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.auto_color_button)
        key_layout.addLayout(color_row)

        self.color_swatch = QFrame()
        self.color_swatch.setFixedHeight(28)
        self.color_swatch.setFrameShape(QFrame.Shape.StyledPanel)
        key_layout.addWidget(self.color_swatch)
        self._update_color_swatch()

        hint = QLabel('You can also click directly on the background in the Original tab.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #8f96a3;')
        key_layout.addWidget(hint)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('Mask Mode'))
        self.keying_mode_combo = QComboBox()
        self.keying_mode_combo.addItem('Automatic', 'auto')
        self.keying_mode_combo.addItem('Global Chroma', 'global')
        self.keying_mode_combo.addItem('Connected to Borders', 'edge_connected')
        self.keying_mode_combo.currentIndexChanged.connect(self._on_keying_mode_changed)
        mode_row.addWidget(self.keying_mode_combo, 1)
        key_layout.addLayout(mode_row)

        self.background_diagnostic_label = QLabel('Background diagnostics: no video analyzed.')
        self.background_diagnostic_label.setWordWrap(True)
        self.background_diagnostic_label.setStyleSheet(
            'QLabel { color: #f4f6f8; padding: 7px; background: #252b33; border: 1px solid #555; }'
        )
        key_layout.addWidget(self.background_diagnostic_label)

        self.tolerance_slider = self._add_labeled_slider(key_layout, 'Tolerance', 0, 100, self.chroma_settings.tolerance)
        self.softness_slider = self._add_labeled_slider(key_layout, 'Edge Softness', 0, 80, self.chroma_settings.softness)
        self.cleanup_slider = self._add_labeled_slider(key_layout, 'Cleanup', 0, 4, self.chroma_settings.cleanup_radius)
        self.decontam_slider = self._add_labeled_slider(key_layout, 'Edge Decontamination', 0, 100, self.chroma_settings.edge_decontamination)
        for slider in (self.tolerance_slider, self.softness_slider, self.cleanup_slider, self.decontam_slider):
            slider.valueChanged.connect(self._on_key_settings_changed)

        additional_group = QGroupBox('Additional Background Colors · R5e5-A')
        additional_layout = QVBoxLayout(additional_group)
        additional_hint = QLabel('Up to 16 colors. Each rule can use the main tolerance or its own local tolerance.')
        additional_hint.setWordWrap(True)
        additional_hint.setStyleSheet('color: #8f96a3;')
        additional_layout.addWidget(additional_hint)
        self.additional_colors_list = QListWidget()
        self.additional_colors_list.setMinimumHeight(96)
        additional_layout.addWidget(self.additional_colors_list)
        additional_row_1 = QHBoxLayout()
        add_color_button = QPushButton('+ Add Color')
        sample_color_button = QPushButton('+ Sample from Frame')
        add_color_button.clicked.connect(lambda: self.background_rules.add_via_picker())
        sample_color_button.clicked.connect(lambda: self.background_rules.arm_sample())
        additional_row_1.addWidget(add_color_button)
        additional_row_1.addWidget(sample_color_button)
        additional_layout.addLayout(additional_row_1)
        additional_row_2 = QHBoxLayout()
        toggle_color_button = QPushButton('Enable / Disable')
        tolerance_color_button = QPushButton('Tolerance')
        remove_color_button = QPushButton('Remove')
        clear_colors_button = QPushButton('Svuota')
        toggle_color_button.clicked.connect(lambda: self.background_rules.toggle_selected())
        tolerance_color_button.clicked.connect(lambda: self.background_rules.set_selected_tolerance())
        remove_color_button.clicked.connect(lambda: self.background_rules.remove_selected())
        clear_colors_button.clicked.connect(lambda: self.background_rules.clear())
        additional_row_2.addWidget(toggle_color_button)
        additional_row_2.addWidget(tolerance_color_button)
        additional_row_2.addWidget(remove_color_button)
        additional_row_2.addWidget(clear_colors_button)
        additional_layout.addLayout(additional_row_2)
        key_layout.addWidget(additional_group)

        structural_group = QGroupBox('Structural Refinement · R5e5-B')
        structural_form = QFormLayout(structural_group)
        self.outer_border_checkbox = QCheckBox('Include outer border in mask')
        self.outer_border_spin = QSpinBox()
        self.outer_border_spin.setRange(0, 256)
        self.outer_border_spin.setValue(8)
        self.outer_border_spin.setSuffix(' px')
        self.outer_border_spin.setEnabled(False)
        self.subject_expand_checkbox = QCheckBox('Expand background toward subject')
        self.subject_expand_spin = QSpinBox()
        self.subject_expand_spin.setRange(0, 16)
        self.subject_expand_spin.setValue(2)
        self.subject_expand_spin.setSuffix(' px')
        self.subject_expand_spin.setEnabled(False)
        self.structural_diagnostic_label = QLabel('Structural refinement disabled.')
        self.structural_diagnostic_label.setWordWrap(True)
        self.structural_diagnostic_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #252a30; border: 1px solid #4b5560; }')
        structural_form.addRow('', self.outer_border_checkbox)
        structural_form.addRow('Border Thickness', self.outer_border_spin)
        structural_form.addRow('', self.subject_expand_checkbox)
        structural_form.addRow('Subject Edge Erosion', self.subject_expand_spin)
        structural_form.addRow('Diagnostics', self.structural_diagnostic_label)
        self.outer_border_checkbox.toggled.connect(self._on_structural_mask_settings_changed)
        self.outer_border_spin.valueChanged.connect(self._on_structural_mask_settings_changed)
        self.subject_expand_checkbox.toggled.connect(self._on_structural_mask_settings_changed)
        self.subject_expand_spin.valueChanged.connect(self._on_structural_mask_settings_changed)
        key_layout.addWidget(structural_group)

        profiles_group = QGroupBox('Alpha / Chroma Profiles')
        profiles_group.setMinimumWidth(360)
        profiles_layout = QVBoxLayout(profiles_group)
        profiles_layout.setContentsMargins(12, 16, 12, 12)
        profiles_layout.setSpacing(8)
        self.chroma_profile_combo = QComboBox()
        self.chroma_profile_combo.setMinimumWidth(300)
        self.chroma_profile_combo.setMinimumHeight(30)
        load_profile_button = QPushButton('Load Profile')
        load_profile_button.setMinimumHeight(30)
        load_profile_button.clicked.connect(lambda: self.chroma_profiles.load_selected())
        save_profile_button = QPushButton('Save Current Profile')
        save_profile_button.setMinimumHeight(30)
        save_profile_button.clicked.connect(lambda: self.chroma_profiles.save_current_as())
        delete_profile_button = QPushButton('Delete Profile')
        delete_profile_button.setMinimumHeight(30)
        delete_profile_button.clicked.connect(lambda: self.chroma_profiles.delete_selected())
        profile_buttons_row = QHBoxLayout()
        profile_buttons_row.setSpacing(8)
        profile_buttons_row.addWidget(load_profile_button)
        profile_buttons_row.addWidget(delete_profile_button)
        profiles_layout.addWidget(self.chroma_profile_combo)
        profiles_layout.addLayout(profile_buttons_row)
        profiles_layout.addWidget(save_profile_button)
        key_layout.addWidget(profiles_group)
        layout.addWidget(key_group)

        export_group = QGroupBox('R1 Export')
        export_form = QFormLayout(export_group)
        self.format_combo = QComboBox()
        self.format_combo.addItems(['PNG', 'WebP lossless'])
        self.crop_checkbox = QCheckBox('Crop to Subject')
        self.crop_checkbox.setChecked(True)
        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(0, 128)
        self.padding_spin.setValue(8)
        export_form.addRow('Format', self.format_combo)
        export_form.addRow('', self.crop_checkbox)
        export_form.addRow('Margin px', self.padding_spin)
        layout.addWidget(export_group)

        selection_group = QGroupBox('Selected Frames')
        selection_layout = QVBoxLayout(selection_group)
        self.selection_list = QListWidget()
        self.selection_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.selection_list.itemDoubleClicked.connect(lambda item: self._set_frame(int(item.data(Qt.ItemDataRole.UserRole))))
        selection_layout.addWidget(self.selection_list)
        selection_buttons = QHBoxLayout()
        add_button = QPushButton('Add')
        add_button.clicked.connect(self._add_current_frame)
        remove_button = QPushButton('Remove')
        remove_button.clicked.connect(self._remove_selected_frames)
        selection_buttons.addWidget(add_button)
        selection_buttons.addWidget(remove_button)
        selection_layout.addLayout(selection_buttons)
        layout.addWidget(selection_group, 1)

        for label, idx in (
            ('Go to Project →', 0),
            ('Go to Generate →', 1),
            ('Go to Clean-up R3b →', 3),
            ('Go to R2 Alignment →', 4),
            ('Analyze and Try R3 Selection →', 5),
            ('Go to Export Studio R5e4 →', 6),
        ):
            b = QPushButton(label)
            b.clicked.connect(lambda checked=False, tab=idx: self.workspace_tabs.setCurrentIndex(tab))
            layout.addWidget(b)
        return panel

    def _add_labeled_slider(self, parent_layout: QVBoxLayout, title: str, minimum: int, maximum: int, value: int) -> QSlider:
        row = QHBoxLayout()
        label = QLabel(title)
        value_label = QLabel(str(value))
        value_label.setMinimumWidth(32)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(value_label)
        parent_layout.addLayout(row)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.valueChanged.connect(lambda current, target=value_label: target.setText(str(current)))
        parent_layout.addWidget(slider)
        return slider

    def _build_timeline(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.valueChanged.connect(self._set_frame)
        self.frame_spin = QSpinBox()
        self.frame_spin.setRange(0, 0)
        self.frame_spin.valueChanged.connect(self._set_frame)
        self.time_label = QLabel('00:00.000 / 00:00.000')
        self.time_label.setMinimumWidth(190)
        layout.addWidget(QLabel('Timeline'))
        layout.addWidget(self.frame_slider, 1)
        layout.addWidget(QLabel('Frame'))
        layout.addWidget(self.frame_spin)
        layout.addWidget(self.time_label)
        return widget

    def _set_video_controls_enabled(self, enabled: bool) -> None:
        self._video_controls_available = bool(enabled)
        self._refresh_command_context()

    def _open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Open Video', '', 'MP4 Video (*.mp4 *.m4v);;Video (*.mp4 *.m4v *.mov *.avi *.webm);;All Files (*)')
        if not path:
            return
        self._open_video_path(path)

    def _import_generated_video(self, path: str) -> None:
        if self._open_video_path(path):
            self.workspace_tabs.setCurrentIndex(2)
            self.statusBar().showMessage(f'Generated video imported into R1: {Path(path).name}')

    def _apply_opened_source(self, metadata, *, label: str, select_all: bool = False) -> None:
        self.current_frame_index = 0
        self.selected_frames = list(range(metadata.frame_count)) if select_all else []
        self.rgba_overrides.clear()
        self._refresh_selection_list()
        self.cleanup_studio.set_selected_frames(self.selected_frames)
        self.alignment_studio.clear_project()
        self.smart_studio.clear_project()
        self.smart_studio.set_video_metadata(metadata)
        with QSignalBlocker(self.frame_slider), QSignalBlocker(self.frame_spin):
            self.frame_slider.setRange(0, metadata.frame_count - 1)
            self.frame_spin.setRange(0, metadata.frame_count - 1)
            self.frame_slider.setValue(0)
            self.frame_spin.setValue(0)
        self.file_label.setText(metadata.path.name)
        self.file_label.setToolTip(str(metadata.path))
        self.video_size_label.setText(f'{metadata.width} × {metadata.height}')
        self.outer_border_spin.setMaximum(max(0, min(metadata.width, metadata.height) // 4))
        self.video_fps_label.setText(f'{metadata.fps:.3f}')
        self.video_frames_label.setText(str(metadata.frame_count))
        self.video_duration_label.setText(self._format_time(metadata.duration_seconds))
        self._set_video_controls_enabled(True)
        try:
            first_frame = self.video.get_frame_rgb(0)
            requested = self._load_requested_background_from_job(metadata.path) if self.video.source_kind == 'video' else None
            diagnostic = analyze_background(first_frame, requested_rgb=requested)
            self._apply_background_diagnostic(
                diagnostic,
                auto_apply=bool(requested is not None or (self.video.source_kind == 'video' and not self.chroma_profiles.has_saved_last)),
            )
        except Exception as exc:
            self.background_diagnostic = None
            self.background_diagnostic_label.setText(f'Background diagnostics unavailable: {exc}')
        self._set_frame(0)
        if select_all:
            self.cleanup_studio.set_selected_frames(self.selected_frames)
            self.smart_studio.set_r1_selection(self.selected_frames)
        self.statusBar().showMessage(label)

    def _open_video_path(self, path: str) -> bool:
        self._stop_playback()
        self.cleanup_studio.prepare_source_change()
        try:
            metadata = self.video.open(path)
        except VideoOpenError as exc:
            QMessageBox.critical(self, 'Video Open Error', str(exc))
            return False
        self._apply_opened_source(metadata, label=f'Video opened: {metadata.path.name}', select_all=False)
        return True

    def _open_sequence_manifest_path(self, manifest_path: str, *, select_all: bool = False) -> bool:
        self._stop_playback()
        self.cleanup_studio.prepare_source_change()
        try:
            metadata = self.video.open_sequence_manifest(manifest_path)
        except VideoOpenError as exc:
            QMessageBox.critical(self, 'Sprite Sequence Error', str(exc))
            return False
        self._apply_opened_source(
            metadata,
            label=f'Sprite sequence opened: {metadata.frame_count} frame',
            select_all=select_all,
        )
        return True

    def _import_spritesheet_sequence(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        manifest_path = payload.get('manifest_path')
        if not manifest_path:
            return
        if self._open_sequence_manifest_path(str(manifest_path), select_all=True):
            self.workspace_tabs.setCurrentIndex(2)
            self._save_active_group_snapshot()
            if hasattr(self, 'workflow_workspace'):
                self.workflow_workspace.refresh_context()
            self.statusBarMessage(f'Spritesheet imported into the pipeline: {self.video.metadata.frame_count} frame.')

    def _use_reference_sheet_in_generate(self, path: str) -> None:
        target = str(Path(path).resolve())
        self.generation_workspace.reference_edit.setText(target)
        self.workspace_tabs.setCurrentIndex(1)
        self._save_active_group_snapshot()
        self.statusBarMessage(f'WAN Reference Sheet loaded in Generate: {Path(target).name}')

    def _use_generated_image_as_reference(self, path: str) -> None:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            self.statusBarMessage('R5e9: generated image is not available.')
            return
        target = source
        store = self.project_workspace.project_store
        group_id = self.project_workspace.active_group_id
        if store is not None and group_id:
            workspace = store.group_workspace(group_id)
            source_dir = workspace / 'source'
            source_dir.mkdir(parents=True, exist_ok=True)
            target = source_dir / 'generated_master.png'
            if source != target.resolve():
                shutil.copy2(source, target)
            source_manifest = getattr(self.image_generation_workspace, 'last_manifest_path', None)
            if source_manifest and Path(str(source_manifest)).is_file():
                manifest_dir = workspace / 'manifests'
                manifest_dir.mkdir(parents=True, exist_ok=True)
                target_manifest = manifest_dir / 'image_generation_manifest.json'
                if Path(str(source_manifest)).resolve() != target_manifest.resolve():
                    shutil.copy2(Path(str(source_manifest)), target_manifest)
                self.image_generation_workspace.last_manifest_path = str(target_manifest.resolve())
            self.image_generation_workspace.last_image_path = str(target.resolve())
        self.generation_workspace.reference_edit.setText(str(target.resolve()))
        self._save_active_group_snapshot()
        self.statusBarMessage(f'R5e9: image automatically loaded as WAN reference: {target.name}')

    def _on_image_generation_job_finished(self, payload: dict) -> None:
        # Image jobs remain separate from Calibration Lab video jobs. Their
        # normalized state is persisted in the active group snapshot instead.
        self._save_active_group_snapshot()
        if hasattr(self, 'workflow_workspace'):
            self.workflow_workspace.refresh_context()

    def _set_frame(self, frame_index: int) -> None:
        if not self.video.is_open:
            return
        metadata = self.video.metadata
        index = min(max(int(frame_index), 0), metadata.frame_count - 1)
        try:
            frame = self.video.get_frame_rgb(index)
        except VideoOpenError as exc:
            self._stop_playback()
            QMessageBox.critical(self, 'Decode Error', str(exc))
            return
        self.current_frame_index = index
        self.current_frame_rgb = frame
        with QSignalBlocker(self.frame_slider), QSignalBlocker(self.frame_spin):
            self.frame_slider.setValue(index)
            self.frame_spin.setValue(index)
        current_seconds = metadata.frame_time_seconds(index)
        self.time_label.setText(f'{self._format_time(current_seconds)} / {self._format_time(metadata.duration_seconds)}')
        self._refresh_previews()

    @perf_instrument('ui.main_window.refresh_previews')
    def _refresh_previews(self) -> None:
        frame = self.current_frame_rgb
        if frame is None:
            return
        try:
            override = self.get_rgba_override(self.current_frame_index)
            if override is not None:
                rgba = override
                mask = rgba[:, :, 3]
                _structural_mask, diagnostic = create_alpha_mask_with_diagnostics(frame, self.chroma_settings)
            else:
                rgba, mask, diagnostic = apply_chroma_key_with_diagnostics(frame, self.chroma_settings)
            checker = render_checkerboard(rgba)
        except Exception as exc:
            self.statusBar().showMessage(f'Processing error: {exc}')
            return
        self.original_preview.set_preview_pixmap(self._numpy_to_pixmap(frame), frame.shape[1], frame.shape[0])
        mask_rgb = np.repeat(mask[:, :, None], 3, axis=2)
        self.mask_preview.set_preview_pixmap(self._numpy_to_pixmap(mask_rgb), mask.shape[1], mask.shape[0])
        self.result_preview.set_preview_pixmap(self._numpy_to_pixmap(checker), checker.shape[1], checker.shape[0])
        subject_rgb = np.repeat(diagnostic.subject_mask[:, :, None], 3, axis=2)
        background_rgb = np.repeat(diagnostic.background_candidate[:, :, None], 3, axis=2)
        self.subject_preview.set_preview_pixmap(self._numpy_to_pixmap(subject_rgb), subject_rgb.shape[1], subject_rgb.shape[0])
        self.background_candidate_preview.set_preview_pixmap(self._numpy_to_pixmap(background_rgb), background_rgb.shape[1], background_rgb.shape[0])
        if self.subject_expand_checkbox.isChecked() and not diagnostic.subject_detected:
            self.structural_diagnostic_label.setText('⚠ Central subject could not be detected reliably. Expansion toward the subject was NOT applied.')
            self.structural_diagnostic_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #3b3020; border: 1px solid #9b7135; }')
        elif diagnostic.subject_detected:
            self.structural_diagnostic_label.setText(
                f'Silhouette: {diagnostic.subject_confidence} · {diagnostic.subject_reason}. Forced border: {diagnostic.outer_border_mask_px}px · expansion: {diagnostic.subject_edge_mask_expand_px}px.'
            )
            self.structural_diagnostic_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #20382a; border: 1px solid #3d7b55; }')
        else:
            self.structural_diagnostic_label.setText('No reliable central subject detected; no structural erosion was applied.')
            self.structural_diagnostic_label.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #252a30; border: 1px solid #4b5560; }')


    def _on_key_settings_changed(self) -> None:
        self.chroma_settings.tolerance = self.tolerance_slider.value()
        self.chroma_settings.softness = self.softness_slider.value()
        self.chroma_settings.cleanup_radius = self.cleanup_slider.value()
        self.chroma_settings.edge_decontamination = self.decontam_slider.value()
        self.chroma_profiles.remember_current()
        self.preview_debounce.start(55)
        self.alignment_studio.mark_dirty()
        self.smart_studio.mark_dirty()
        self.cleanup_studio.set_selected_frames(self.selected_frames)

    def _on_structural_mask_settings_changed(self, *_args) -> None:
        self.outer_border_spin.setEnabled(self.outer_border_checkbox.isChecked())
        self.subject_expand_spin.setEnabled(self.subject_expand_checkbox.isChecked())
        self.chroma_settings.outer_border_mask_px = (
            int(self.outer_border_spin.value()) if self.outer_border_checkbox.isChecked() else 0
        )
        self.chroma_settings.subject_edge_mask_expand_px = (
            int(self.subject_expand_spin.value()) if self.subject_expand_checkbox.isChecked() else 0
        )
        self.chroma_profiles.remember_current()
        self.preview_debounce.start(55)
        self.alignment_studio.mark_dirty()
        self.smart_studio.mark_dirty()
        self.cleanup_studio.set_selected_frames(self.selected_frames)

    def _choose_background_color(self) -> None:
        initial = QColor(*self.chroma_settings.background_rgb)
        color = QColorDialog.getColor(initial, self, 'Background Color')
        if not color.isValid():
            return
        self.chroma_settings.background_rgb = (color.red(), color.green(), color.blue())
        self.chroma_profiles.remember_current()
        self._update_color_swatch()
        self._refresh_previews()
        self.alignment_studio.mark_dirty()
        self.smart_studio.mark_dirty()
        self.cleanup_studio.set_selected_frames(self.selected_frames)

    def _auto_detect_background(self) -> None:
        if self.current_frame_rgb is None:
            return
        diagnostic = analyze_background(
            self.current_frame_rgb,
            requested_rgb=self.chroma_settings.requested_background_rgb,
        )
        self._apply_background_diagnostic(diagnostic, auto_apply=True)
        self.chroma_profiles.remember_current()
        self._refresh_previews()
        self.alignment_studio.mark_dirty()
        self.smart_studio.mark_dirty()
        self.cleanup_studio.set_selected_frames(self.selected_frames)
        self.statusBar().showMessage(
            f'Background applied: RGB {diagnostic.detected_rgb}; recommended mode {diagnostic.recommended_mode}.'
        )

    def _sample_background_from_frame(self, x: int, y: int) -> None:
        if self.current_frame_rgb is None:
            return
        pixel = self.current_frame_rgb[y, x]
        color = tuple(int(value) for value in pixel)
        if self.background_rules.try_consume_sample(color, x, y):
            return
        self.chroma_settings.background_rgb = color
        self.chroma_profiles.remember_current()
        self._update_color_swatch()
        self._refresh_previews()
        self.alignment_studio.mark_dirty()
        self.smart_studio.mark_dirty()
        self.cleanup_studio.set_selected_frames(self.selected_frames)
        self.statusBar().showMessage(f'Main color sampled at ({x}, {y}): RGB {color}')

    def _update_color_swatch(self) -> None:
        r, g, b = self.chroma_settings.background_rgb
        text_color = '#000000' if (r * 299 + g * 587 + b * 114) > 150000 else '#ffffff'
        self.color_swatch.setStyleSheet(f'QFrame {{ background: rgb({r}, {g}, {b}); border: 1px solid #555; color: {text_color}; }}')
        self.color_swatch.setToolTip(f'RGB ({r}, {g}, {b})')

    def _on_keying_mode_changed(self) -> None:
        self.chroma_settings.keying_mode = str(self.keying_mode_combo.currentData())
        self.chroma_profiles.remember_current()
        self._refresh_previews()
        self.alignment_studio.mark_dirty()
        self.smart_studio.mark_dirty()
        self.cleanup_studio.set_selected_frames(self.selected_frames)

    @staticmethod
    def _load_requested_background_from_job(video_path: Path) -> tuple[int, int, int] | None:
        candidates = [
            video_path.parent.parent / 'request.json',
            video_path.parent.parent / 'generation_manifest.json',
        ]
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding='utf-8'))
            except Exception:
                continue
            values = None
            if candidate.name == 'request.json':
                values = payload.get('metadata', {}).get('requested_background_rgb')
            else:
                values = payload.get('metadata', {}).get('requested_background_rgb')
                if values is None:
                    values = payload.get('background_contract', {}).get('requested_rgb')
            if isinstance(values, (list, tuple)) and len(values) == 3:
                return tuple(int(max(0, min(255, value))) for value in values)
        return None

    def _apply_background_diagnostic(self, diagnostic, *, auto_apply: bool) -> None:
        self.background_diagnostic = diagnostic
        self.chroma_settings.requested_background_rgb = diagnostic.requested_rgb
        self.chroma_settings.detected_background_rgb = diagnostic.detected_rgb
        self.chroma_settings.background_distance = diagnostic.lab_distance
        self.chroma_settings.background_mismatch = diagnostic.mismatch
        if auto_apply:
            self.chroma_settings.background_rgb = diagnostic.detected_rgb
            self.chroma_settings.keying_mode = 'auto'
            with QSignalBlocker(self.keying_mode_combo):
                self.keying_mode_combo.setCurrentIndex(0)
            self._update_color_swatch()

        requested_text = (
            f'RGB {diagnostic.requested_rgb}'
            if diagnostic.requested_rgb is not None
            else 'not specified'
        )
        mismatch_text = 'YES' if diagnostic.mismatch else 'no'
        mode_text = 'connected to borders' if diagnostic.recommended_mode == 'edge_connected' else 'global chroma'
        distance_text = '—' if diagnostic.lab_distance is None else f'{diagnostic.lab_distance:.1f}'
        self.background_diagnostic_label.setText(
            f'Requested background: {requested_text}\nDetected background: RGB {diagnostic.detected_rgb}\nColor distance: {distance_text} · mismatch: {mismatch_text}\nCorner uniformity: {diagnostic.confidence} · recommended mode: {mode_text}'
        )
        if diagnostic.mismatch:
            self.background_diagnostic_label.setStyleSheet(
                'QLabel { color: #f4f6f8; padding: 7px; background: #3b3020; border: 1px solid #9b7135; }'
            )
        else:
            self.background_diagnostic_label.setStyleSheet(
                'QLabel { color: #f4f6f8; padding: 7px; background: #20382a; border: 1px solid #3d7b55; }'
            )

    def _toggle_playback(self) -> None:
        if not self.video.is_open:
            return
        if self.play_timer.isActive():
            self._stop_playback()
            return
        interval_ms = max(1, int(round(1000.0 / self.video.metadata.fps)))
        self.play_timer.start(interval_ms)
        self.play_action.setText('Pause')

    def _stop_playback(self) -> None:
        self.play_timer.stop()
        if hasattr(self, 'play_action'):
            self.play_action.setText('Play')

    def _advance_playback(self) -> None:
        if not self.video.is_open:
            self._stop_playback()
            return
        next_index = self.current_frame_index + 1
        if next_index >= self.video.metadata.frame_count:
            self._stop_playback()
            return
        self._set_frame(next_index)

    def _add_current_frame(self) -> None:
        if not self.video.is_open:
            return
        current = self.current_frame_index
        if current not in self.selected_frames:
            self.selected_frames.append(current)
            self.selected_frames.sort()
            self._refresh_selection_list()
            self._set_frame(current)
            self.statusBar().showMessage(f'Frame {current} added. The timeline remains on the current frame.')
        else:
            self._set_frame(current)
            self.statusBar().showMessage(f'Frame {current} already present in the selection.')

    def _remove_selected_frames(self) -> None:
        items = self.selection_list.selectedItems()
        if not items:
            return
        indices = {int(item.data(Qt.ItemDataRole.UserRole)) for item in items}
        self.selected_frames = [index for index in self.selected_frames if index not in indices]
        self._refresh_selection_list()

    def _refresh_selection_list(self) -> None:
        current = self.current_frame_index
        self.selection_list.clear()
        if self.video.is_open:
            metadata = self.video.metadata
            for index in self.selected_frames:
                seconds = metadata.frame_time_seconds(index)
                item_text = f'Frame {index:06d}   ·   {self._format_time(seconds)}'
                self.selection_list.addItem(item_text)
                item = self.selection_list.item(self.selection_list.count() - 1)
                item.setData(Qt.ItemDataRole.UserRole, index)
        self.cleanup_studio.set_selected_frames(self.selected_frames)
        self.alignment_studio.set_selected_frames(self.selected_frames)
        self.smart_studio.set_r1_selection(self.selected_frames)
        if self.video.is_open:
            self._set_frame(current)

    def _export_frames(self) -> None:
        if not self.video.is_open:
            return
        if not self.selected_frames:
            QMessageBox.information(self, 'No Frames', 'Add at least one frame to the selection.')
            return
        output_dir = QFileDialog.getExistingDirectory(self, 'Export Folder', str(self.video.metadata.path.parent))
        if not output_dir:
            return
        output_format = 'png' if self.format_combo.currentIndex() == 0 else 'webp'
        export_settings = ExportSettings(output_format=output_format, crop_to_subject=self.crop_checkbox.isChecked(), padding=self.padding_spin.value(), webp_quality=95)
        progress = QProgressDialog('Exporting frames…', 'Cancel', 0, len(self.selected_frames), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        cancelled = False

        def on_progress(position: int, total: int, frame_index: int) -> None:
            nonlocal cancelled
            progress.setLabelText(f'Exporting frame {frame_index} ({position}/{total})')
            progress.setValue(position)
            QApplication.processEvents()
            if progress.wasCanceled():
                cancelled = True
                raise ExportError('Export cancelled by the user.')

        try:
            manifest = export_selected_frames(
                frame_indices=self.selected_frames,
                frame_loader=self.video.get_frame_rgb,
                video_metadata=self.video.metadata,
                chroma_settings=self.chroma_settings,
                export_settings=export_settings,
                output_directory=output_dir,
                progress_callback=on_progress,
                rgba_override_provider=self.get_rgba_override,
            )
        except (ExportError, EmptySubjectError, VideoOpenError, OSError, ValueError) as exc:
            progress.close()
            if cancelled:
                self.statusBar().showMessage('Export cancelled.')
            else:
                QMessageBox.critical(self, 'Export Error', str(exc))
            return
        progress.setValue(len(self.selected_frames))
        progress.close()
        QMessageBox.information(self, 'Export completed', f"Exported {len(manifest['frames'])} frames in:\n{output_dir}\n\nexport-manifest.json was also created.")
        self.statusBar().showMessage('R1 export completed.')

    def _apply_smart_selection(self, indices: list[int]) -> None:
        if not self.video.is_open:
            return
        normalized = sorted(set(int(index) for index in indices if 0 <= int(index) < self.video.metadata.frame_count))
        if not normalized:
            return
        self.selected_frames = normalized
        self._refresh_selection_list()
        self.statusBar().showMessage(f'R1 selection updated from R3: {len(normalized)} frame.')

    def _on_workspace_changed(self, index: int) -> None:
        if index == 3:
            self._stop_playback()
            self.smart_studio.player.stop()
            self.cleanup_studio.set_selected_frames(self.selected_frames)
        elif index == 4:
            self._stop_playback()
            self.smart_studio.player.stop()
            self.alignment_studio.ensure_prepared()
        elif index == 5:
            self._stop_playback()
            self.smart_studio.set_r1_selection(self.selected_frames)
        elif index == 6:
            self._stop_playback()
            self.smart_studio.player.stop()
        elif index == 7:
            self._stop_playback()
            self.smart_studio.player.stop()
            self.production_presets_workspace.refresh_context()
        elif index == 8:
            self._stop_playback()
            self.smart_studio.player.stop()
            self.calibration_workspace.refresh_context(auto_sync=True)
        elif index in (9, 10, 11):
            self._stop_playback()
            self.smart_studio.player.stop()
        elif index == 12:
            self._stop_playback()
            self.smart_studio.player.stop()
            self._save_active_group_snapshot()
            self.workflow_workspace.refresh_context()
        elif index == 13:
            self._stop_playback()
            self.smart_studio.player.stop()
        self._refresh_command_context()

    @staticmethod
    def _numpy_to_pixmap(image_rgb: np.ndarray) -> QPixmap:
        contiguous = np.ascontiguousarray(image_rgb)
        height, width, channels = contiguous.shape
        if channels != 3:
            raise ValueError('The preview requires an RGB image.')
        qimage = QImage(contiguous.data, width, height, contiguous.strides[0], QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(qimage)

    def _build_raw_export_payload(self) -> dict:
        if not self.video.is_open:
            raise RuntimeError('Open a video before using Export Studio.')
        if not self.selected_frames:
            raise RuntimeError('No frames selected in R1.')
        rgba_frames = []
        for frame_index in self.selected_frames:
            override = self.get_rgba_override(frame_index)
            if override is not None:
                rgba = override.copy()
            else:
                source_rgb = self.video.get_frame_rgb(frame_index)
                rgba, _ = apply_chroma_key(source_rgb, self.chroma_settings)
            rgba_frames.append(rgba)
        return {
            'rgba_frames': rgba_frames,
            'default_base_name': 'selection-r1',
            'suggested_output_dir': str(self.video.metadata.path.parent),
            'metadata': {
                'source_video': str(self.video.metadata.path),
                'selected_frame_indices': list(self.selected_frames),
                'chroma': self.chroma_settings.to_dict(),
                'kind': 'raw-r1',
            },
        }

    def _build_aligned_export_payload(self) -> dict:
        return self.alignment_studio.build_export_payload()

    def _load_calibration_profile_in_generate(self, profile: dict) -> None:
        self.generation_workspace.apply_generation_profile(profile, persist_last=True)
        self.workspace_tabs.setCurrentIndex(1)
        self.statusBarMessage('Calibration Lab: configuration loaded into the Generate workspace.')

    def _load_prompt_profile_in_generate(self, profile: dict) -> None:
        self.generation_workspace.apply_generation_profile(profile, persist_last=True)
        self.workspace_tabs.setCurrentIndex(1)
        self.statusBarMessage('Prompt Builder R5e7: prompt applied to the Generate workspace.')

    def _active_group_context(self) -> dict | None:
        store = self.project_workspace.project_store
        group_id = self.project_workspace.active_group_id
        if store is None or not group_id:
            return None
        group = store.get_group(group_id)
        if group is None:
            return None
        group = dict(group)
        group['label'] = store.group_label(group_id)
        return group

    def _current_pipeline_for_preset(self) -> dict:
        group_id = self.project_workspace.active_group_id
        if not group_id:
            return {}
        snapshot = self._capture_pipeline_snapshot(group_id=group_id)
        pipeline = snapshot.get('pipeline_state')
        return dict(pipeline) if isinstance(pipeline, dict) else {}

    @staticmethod
    def _direction_name_for_alignment(value: str) -> str:
        mapping = {
            'N': 'north', 'NE': 'north-east', 'E': 'east', 'SE': 'south-east',
            'S': 'south', 'SW': 'south-west', 'W': 'west', 'NW': 'north-west',
        }
        key = str(value).strip().upper()
        return mapping.get(key, str(value).strip().lower())

    def _apply_production_preset(self, preset_name: str, preset: dict, sections: list[str]) -> None:
        store = self.project_workspace.project_store
        group_id = self.project_workspace.active_group_id
        if store is None or not group_id:
            raise RuntimeError('No active Project Group.')

        # Commit the live context first so the merge starts from the latest group state.
        self._save_active_group_snapshot()
        group = store.get_group(group_id)
        if group is None:
            raise RuntimeError('The active group is no longer available.')
        current_pipeline = group.get('pipeline_state') if isinstance(group.get('pipeline_state'), dict) else {}
        merged = merge_preset_into_pipeline(current_pipeline, preset, sections)

        # Group identity always wins over portable preset labels.
        lineage = store.group_lineage(group_id)
        animation_name = next((item['name'] for item in lineage if item.get('type') == 'animation'), None)
        direction_name = next((item['name'] for item in lineage if item.get('type') == 'direction'), None)
        alignment = merged.get('alignment')
        if isinstance(alignment, dict):
            profile = alignment.setdefault('profile', {})
            if isinstance(profile, dict):
                if animation_name:
                    profile['animation_name'] = str(animation_name).strip().lower()
                if direction_name:
                    profile['direction'] = self._direction_name_for_alignment(str(direction_name))

        export_state = merged.get('export')
        if isinstance(export_state, dict):
            studio = export_state.get('studio')
            if isinstance(studio, dict):
                slug_parts = [str(item['name']).strip().lower().replace(' ', '-') for item in lineage if item.get('type') in {'animation', 'direction'}]
                if slug_parts:
                    studio['base_name'] = '-'.join(slug_parts)

        store.update_group_snapshot(group_id, {
            'assets': group.get('assets', {}),
            'pipeline_state': merged,
        })
        store.assign_production_preset(group_id, preset_name, sections=sections)
        self.project_workspace._refresh_view(select_group_id=group_id)
        self._on_active_group_changed(group_id)
        self.production_presets_workspace.refresh_context()

    def _capture_pipeline_snapshot(self, *, group_id: str | None = None) -> dict:
        image_path = getattr(self.image_generation_workspace, 'last_image_path', None)
        image_manifest_path = getattr(self.image_generation_workspace, 'last_manifest_path', None)
        image_manifest = str(Path(str(image_manifest_path)).resolve()) if image_manifest_path and Path(str(image_manifest_path)).is_file() else None
        assets = {
            'reference_image': self.generation_workspace.reference_edit.text().strip() or None,
            'generated_image': str(Path(str(image_path)).resolve()) if image_path else None,
            'image_generation_manifest': image_manifest,
            'motion_reference': self.generation_workspace.motion_edit.text().strip() or None,
            'source_video': (str(self.video.metadata.path) if self.video.is_open and self.video.source_kind == 'video' else None),
            'source_sequence_manifest': (str(self.video.sequence_manifest_path) if self.video.is_open and self.video.source_kind == 'sequence' and self.video.sequence_manifest_path is not None else None),
            'source_spritesheet': (str(self.video.metadata.path) if self.video.is_open and self.video.source_kind == 'sequence' else None),
        }
        cleanup_state: dict = {'frame_indices': sorted(self.rgba_overrides.keys()), 'override_file': None}
        if group_id and self.project_workspace.project_store is not None:
            workspace = self.project_workspace.project_store.group_workspace(group_id)
            cleanup_dir = workspace / 'cleanup'
            cleanup_dir.mkdir(parents=True, exist_ok=True)
            override_path = cleanup_dir / 'rgba_overrides.npz'
            if self.rgba_overrides:
                np.savez_compressed(override_path, **{f'frame_{index}': rgba for index, rgba in sorted(self.rgba_overrides.items())})
                cleanup_state['override_file'] = str(override_path.relative_to(workspace).as_posix())
            elif override_path.exists():
                override_path.unlink()
        export_state = {
            'r1': {
                'format_index': self.format_combo.currentIndex(),
                'crop_to_subject': self.crop_checkbox.isChecked(),
                'padding': self.padding_spin.value(),
            },
            'studio': self.export_studio.snapshot_state(),
        }
        return {
            'assets': assets,
            'pipeline_state': {
                'generation': self.generation_workspace.snapshot_state(),
                'image_generation': self.image_generation_workspace.snapshot_state(),
                'chroma': self.chroma_profiles.capture_profile_data(),
                'selection': {
                    'selected_frames': list(self.selected_frames),
                    'smart_selection': self.smart_studio.snapshot_state(),
                },
                'cleanup': cleanup_state,
                'alignment': self.alignment_studio.snapshot_session(),
                'export': export_state,
            },
        }

    def _capture_project_snapshot(self) -> dict:
        return self._capture_pipeline_snapshot(group_id=None)

    def _save_project_snapshot(self) -> None:
        if self.project_workspace.current_project_path is None:
            QMessageBox.information(self, 'No Project', 'Create or open a project before saving the snapshot.')
            return
        self.project_workspace.update_project_snapshot(self._capture_project_snapshot())
        self._save_active_group_snapshot()

    def _save_active_group_snapshot(self) -> None:
        group_id = self.project_workspace.active_group_id
        if not group_id or self.project_workspace.project_store is None:
            return
        self.project_workspace.update_active_group_snapshot(self._capture_pipeline_snapshot(group_id=group_id))

    def _on_active_group_will_change(self, old_group_id: str, new_group_id: str) -> None:
        if old_group_id:
            self._save_active_group_snapshot()
        self.cleanup_studio.prepare_source_change()
        self.cleanup_studio.reset_context_history()

    def _clear_loaded_video_context(self) -> None:
        self._stop_playback()
        self.cleanup_studio.prepare_source_change()
        self.video.close()
        self.current_frame_index = 0
        self.current_frame_rgb = None
        self.selected_frames.clear()
        self.rgba_overrides.clear()
        self._refresh_selection_list()
        self.cleanup_studio.set_selected_frames([])
        self.alignment_studio.clear_project()
        self.smart_studio.clear_project()
        self._set_video_controls_enabled(False)
        with QSignalBlocker(self.frame_slider), QSignalBlocker(self.frame_spin):
            self.frame_slider.setRange(0, 0)
            self.frame_spin.setRange(0, 0)
            self.frame_slider.setValue(0)
            self.frame_spin.setValue(0)
        self.file_label.setText('—')
        self.file_label.setToolTip('')
        self.video_size_label.setText('—')
        self.video_fps_label.setText('—')
        self.video_frames_label.setText('—')
        self.video_duration_label.setText('—')
        for preview in (self.original_preview, self.mask_preview, self.result_preview, self.subject_preview, self.background_candidate_preview):
            preview.clear_preview()

    def _load_cleanup_overrides_for_group(self, group_id: str, cleanup_state: dict) -> None:
        self.rgba_overrides.clear()
        if self.project_workspace.project_store is None or not isinstance(cleanup_state, dict):
            return
        relative = cleanup_state.get('override_file')
        if not relative:
            return
        path = self.project_workspace.project_store.group_workspace(group_id) / str(relative)
        if not path.exists():
            return
        try:
            with np.load(path, allow_pickle=False) as payload:
                for key in payload.files:
                    if not key.startswith('frame_'):
                        continue
                    index = int(key.split('_', 1)[1])
                    value = np.asarray(payload[key], dtype=np.uint8)
                    if value.ndim == 3 and value.shape[2] == 4:
                        self.rgba_overrides[index] = value.copy()
        except Exception as exc:
            self.statusBarMessage(f'Group clean-up state could not be restored: {exc}')

    def _on_active_group_changed(self, group_id: str) -> None:
        if not group_id:
            self._clear_loaded_video_context()
            if hasattr(self, 'image_generation_workspace'):
                self.image_generation_workspace.reset_context()
            if hasattr(self, 'production_presets_workspace'):
                self.production_presets_workspace.refresh_context()
            if hasattr(self, 'calibration_workspace'):
                self.calibration_workspace.refresh_context(auto_sync=False)
            if hasattr(self, 'workflow_workspace'):
                self.workflow_workspace.refresh_context()
                self._show_all_workflow_tabs()
            return
        if self.project_workspace.project_store is None:
            return
        group = self.project_workspace.project_store.get_group(group_id)
        if not group:
            return
        pipeline = group.get('pipeline_state', {}) if isinstance(group.get('pipeline_state'), dict) else {}
        assets = group.get('assets', {}) if isinstance(group.get('assets'), dict) else {}

        image_generation_state = pipeline.get('image_generation')
        if isinstance(image_generation_state, dict) and image_generation_state:
            self.image_generation_workspace.apply_state(image_generation_state)
        else:
            self.image_generation_workspace.reset_context()

        generation_state = pipeline.get('generation')
        if isinstance(generation_state, dict) and generation_state:
            self.generation_workspace.apply_state(generation_state)
        else:
            self.generation_workspace.reference_edit.setText(str(assets.get('reference_image') or ''))
            self.generation_workspace.motion_edit.setText(str(assets.get('motion_reference') or ''))

        source_sequence_manifest = assets.get('source_sequence_manifest')
        source_video = assets.get('source_video')
        if source_sequence_manifest and Path(str(source_sequence_manifest)).exists():
            self._open_sequence_manifest_path(str(source_sequence_manifest), select_all=False)
        elif source_video and Path(str(source_video)).exists():
            self._open_video_path(str(source_video))
        else:
            self._clear_loaded_video_context()

        chroma = pipeline.get('chroma')
        if isinstance(chroma, dict) and chroma:
            self.chroma_profiles.apply_profile_data(chroma, persist_last=False)

        cleanup = pipeline.get('cleanup')
        self._load_cleanup_overrides_for_group(group_id, cleanup if isinstance(cleanup, dict) else {})
        if self.current_frame_rgb is not None:
            self._refresh_previews()

        selection = pipeline.get('selection')
        if isinstance(selection, dict):
            frames = selection.get('selected_frames')
            if isinstance(frames, list) and self.video.is_open:
                self.selected_frames = sorted(set(int(v) for v in frames if (isinstance(v, int) or str(v).isdigit()) and 0 <= int(v) < self.video.metadata.frame_count))
                self._refresh_selection_list()
                self.cleanup_studio.set_selected_frames(self.selected_frames)
            smart_state = selection.get('smart_selection')
            if isinstance(smart_state, dict):
                self.smart_studio.apply_state(smart_state)

        alignment = pipeline.get('alignment')
        if isinstance(alignment, dict) and alignment:
            self.alignment_studio.restore_session(alignment)

        export_state = pipeline.get('export')
        if isinstance(export_state, dict):
            r1_state = export_state.get('r1', export_state)
            if isinstance(r1_state, dict):
                self.format_combo.setCurrentIndex(int(r1_state.get('format_index', self.format_combo.currentIndex())))
                self.crop_checkbox.setChecked(bool(r1_state.get('crop_to_subject', self.crop_checkbox.isChecked())))
                self.padding_spin.setValue(int(r1_state.get('padding', self.padding_spin.value())))
            studio_state = export_state.get('studio')
            if isinstance(studio_state, dict):
                self.export_studio.apply_state(studio_state)
        self.statusBarMessage(f'Active context loaded: {self.project_workspace.project_store.group_label(group_id)}')
        if hasattr(self, 'production_presets_workspace'):
            self.production_presets_workspace.refresh_context()
        if hasattr(self, 'calibration_workspace'):
            self.calibration_workspace.refresh_context(auto_sync=True)
        if hasattr(self, 'character_set_workspace'):
            self.character_set_workspace.refresh_context()
        if hasattr(self, 'workflow_workspace'):
            self.workflow_workspace.refresh_context()
            workflow = self.workflow_workspace.current_workflow()
            if workflow is None:
                self._show_all_workflow_tabs()
                self.workspace_tabs.setCurrentIndex(self._workflow_tab_routes['workflow'])
            else:
                self._apply_guided_workflow_tabs(bool(workflow.get('guided_tabs', False)))

    def _on_generation_job_started(self, job_id: str) -> None:
        self._generation_job_groups[str(job_id)] = self.project_workspace.active_group_id

    def _on_generation_job_finished(self, job_payload: dict) -> None:
        job_id = str(job_payload.get('job_id', ''))
        group_id = self._generation_job_groups.pop(job_id, None)
        if not group_id or self.project_workspace.project_store is None:
            return
        if self.project_workspace.project_store.get_group(group_id) is None:
            return
        payload = dict(job_payload)
        job_dir = payload.get('job_directory')
        if job_dir:
            request_path = Path(str(job_dir)) / 'request.json'
            if request_path.exists():
                try:
                    payload['request'] = json.loads(request_path.read_text(encoding='utf-8'))
                except Exception:
                    pass
        self.project_workspace.project_store.append_group_job(group_id, payload)
        self.project_workspace._refresh_view(select_group_id=self.project_workspace.active_group_id)
        if hasattr(self, 'calibration_workspace') and group_id == self.project_workspace.active_group_id:
            self.calibration_workspace.refresh_context(auto_sync=True)
        if hasattr(self, 'workflow_workspace') and group_id == self.project_workspace.active_group_id:
            self.workflow_workspace.refresh_context()

    def _on_export_completed(self, export_payload: dict) -> None:
        if self.project_workspace.active_group_id:
            self.project_workspace.append_export_to_active_group(export_payload)
            self._save_active_group_snapshot()
            if hasattr(self, 'workflow_workspace'):
                self.workflow_workspace.refresh_context()

    def _on_project_changed(self, path: str) -> None:
        self.current_project_path = path
        if hasattr(self, 'character_set_workspace'):
            self.character_set_workspace.refresh_context()
        payload = self.project_workspace.project_store.load() if self.project_workspace.project_store else {}
        # Legacy/global project state remains the fallback when no direction group is active.
        if self.project_workspace.active_group_id:
            self._persist_application_state()
            return
        pipeline_state = payload.get('pipeline_state', {}) if isinstance(payload, dict) else {}
        if isinstance(pipeline_state.get('generation'), dict):
            self.generation_workspace.apply_state(pipeline_state['generation'])
        if isinstance(pipeline_state.get('image_generation'), dict):
            self.image_generation_workspace.apply_state(pipeline_state['image_generation'])
        if isinstance(pipeline_state.get('chroma'), dict):
            self.chroma_profiles.apply_profile_data(pipeline_state['chroma'], persist_last=False)
        alignment = pipeline_state.get('alignment')
        if isinstance(alignment, dict):
            if 'profile' in alignment or 'frame_states' in alignment:
                self.alignment_studio.restore_session(alignment)
            else:
                self.alignment_studio._apply_alignment_profile_data(alignment, persist_last=False)
        export_state = pipeline_state.get('export') if isinstance(pipeline_state, dict) else None
        if isinstance(export_state, dict):
            r1_state = export_state.get('r1', export_state)
            if isinstance(r1_state, dict):
                self.format_combo.setCurrentIndex(int(r1_state.get('format_index', self.format_combo.currentIndex())))
                self.crop_checkbox.setChecked(bool(r1_state.get('crop_to_subject', self.crop_checkbox.isChecked())))
                self.padding_spin.setValue(int(r1_state.get('padding', self.padding_spin.value())))
            studio_state = export_state.get('studio')
            if isinstance(studio_state, dict):
                self.export_studio.apply_state(studio_state)
        assets = payload.get('assets', {}) if isinstance(payload, dict) else {}
        source_sequence_manifest = assets.get('source_sequence_manifest') if isinstance(assets, dict) else None
        source_video = assets.get('source_video') if isinstance(assets, dict) else None
        if source_sequence_manifest and Path(str(source_sequence_manifest)).exists():
            self._open_sequence_manifest_path(str(source_sequence_manifest), select_all=False)
        elif source_video and Path(str(source_video)).exists():
            self._open_video_path(str(source_video))
            selection_state = pipeline_state.get('selection', {}) if isinstance(pipeline_state, dict) else {}
            frames = selection_state.get('selected_frames') if isinstance(selection_state, dict) else None
            if isinstance(frames, list):
                self.selected_frames = sorted(set(int(v) for v in frames if isinstance(v, int) or str(v).isdigit()))
                self._refresh_selection_list()
                self.cleanup_studio.set_selected_frames(self.selected_frames)
        self._persist_application_state()

    def _route_workflow_step(self, route: str) -> None:
        index = self._workflow_tab_routes.get(str(route))
        if index is None:
            self.statusBarMessage(f'R5e10: unrecognized workflow route: {route}')
            return
        self.workspace_tabs.setCurrentIndex(index)

    def _show_all_workflow_tabs(self) -> None:
        for index in range(self.workspace_tabs.count()):
            self.workspace_tabs.setTabVisible(index, True)

    def _apply_guided_workflow_tabs(self, enabled: bool) -> None:
        if not hasattr(self, 'workflow_workspace') or not hasattr(self, '_workflow_tab_routes'):
            return
        workflow = self.workflow_workspace.current_workflow()
        if not enabled or workflow is None:
            self._show_all_workflow_tabs()
            return
        definition = WORKFLOW_DEFINITIONS.get(str(workflow.get('type')))
        if not definition:
            self._show_all_workflow_tabs()
            return
        visible_routes = set(definition.get('visible_routes', set()))
        visible_routes.update({'project', 'workflow'})
        visible_indices = {self._workflow_tab_routes[name] for name in visible_routes if name in self._workflow_tab_routes}
        current = self.workspace_tabs.currentIndex()
        for index in range(self.workspace_tabs.count()):
            self.workspace_tabs.setTabVisible(index, index in visible_indices)
        if current not in visible_indices:
            self.workspace_tabs.setCurrentIndex(self._workflow_tab_routes['workflow'])

    def _save_workflow_settings_checkpoint(self) -> None:
        group_id = self.project_workspace.active_group_id
        store = self.project_workspace.project_store
        if not group_id or store is None:
            QMessageBox.information(self, 'No Group', 'Activate a Project Group before saving the checkpoint.')
            return
        self._save_active_group_snapshot()
        group = store.get_group(group_id)
        if group is None:
            return
        pipeline = group.get('pipeline_state') if isinstance(group.get('pipeline_state'), dict) else {}
        self.workflow_workspace.record_settings_checkpoint(dict(pipeline))
        self.project_workspace._refresh_view(select_group_id=group_id)

    def _promote_current_video_to_motion_reference(self) -> None:
        workflow = self.workflow_workspace.current_workflow() if hasattr(self, 'workflow_workspace') else None
        if workflow is None or workflow.get('type') != 'full':
            QMessageBox.information(self, 'Full workflow required', 'This action belongs to the Full workflow.')
            return
        if not self.video.is_open or self.video.source_kind != 'video':
            QMessageBox.warning(self, 'Video Unavailable', 'Generate or open the intermediate motion video first.')
            return
        store = self.project_workspace.project_store
        group_id = self.project_workspace.active_group_id
        if store is None or not group_id:
            QMessageBox.warning(self, 'No Group', 'Activate a Project Group first.')
            return
        source = Path(self.video.metadata.path).resolve()
        if not source.is_file():
            QMessageBox.warning(self, 'Video Unavailable', 'The current source video is no longer available on disk.')
            return
        workspace = store.group_workspace(group_id)
        motion_dir = workspace / 'motion_references'
        motion_dir.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix.lower() if source.suffix else '.mp4'
        target = motion_dir / f'workflow_motion_reference{suffix}'
        if source != target.resolve():
            shutil.copy2(source, target)
        target = target.resolve()

        # The full workflow must return to the master generated in R5e9 for the final render.
        group_before = store.get_group(group_id) or {}
        assets_before = group_before.get('assets') if isinstance(group_before.get('assets'), dict) else {}
        master = assets_before.get('generated_image') or assets_before.get('reference_image')
        if master and Path(str(master)).exists():
            self.generation_workspace.reference_edit.setText(str(Path(str(master)).resolve()))
        self.generation_workspace.motion_edit.setText(str(target))
        self._save_active_group_snapshot()
        store.update_group(group_id, metadata={
            'workflow_motion_reference': {
                'path': str(target),
                'promoted_from_source_video': str(source),
            }
        })
        self.workflow_workspace.record_motion_reference(path=str(target), promoted_from_source_video=str(source))
        self.project_workspace._refresh_view(select_group_id=group_id)
        self.workspace_tabs.setCurrentIndex(self._workflow_tab_routes['generation'])
        self.statusBarMessage('R5e10: intermediate video promoted to motion reference; master image restored for final generation.')

    def _capture_app_state(self) -> dict:
        return {
            'version': APP_VERSION,
            'current_tab': int(self.workspace_tabs.currentIndex()),
            'current_project_path': self.project_workspace.current_project_path,
            'last_video_path': (str(self.video.metadata.path) if self.video.is_open and self.video.source_kind == 'video' else None),
            'last_sequence_manifest': (str(self.video.sequence_manifest_path) if self.video.is_open and self.video.source_kind == 'sequence' and self.video.sequence_manifest_path is not None else None),
            'generation_workspace': self.generation_workspace.snapshot_state(),
            'chroma': self.chroma_profiles.capture_profile_data(),
            'alignment': self.alignment_studio._capture_alignment_profile_data(),
            'selection': {'selected_frames': list(self.selected_frames)},
            'preferences': (self.theme_preferences.snapshot() if hasattr(self, 'theme_preferences') else {'tab_theme': DEFAULT_TAB_THEME}),
            'export': {
                'r1': {
                    'format_index': self.format_combo.currentIndex(),
                    'crop_to_subject': self.crop_checkbox.isChecked(),
                    'padding': self.padding_spin.value(),
                },
                'studio': self.export_studio.snapshot_state(),
            },
        }

    def _persist_application_state(self) -> None:
        self.profile_store.set_app_state(self._capture_app_state())

    def _restore_app_state(self) -> None:
        state = self.profile_store.get_app_state()
        if not state:
            return
        self.theme_preferences.restore(state.get('preferences'))
        project_path = state.get('current_project_path')
        if isinstance(project_path, str) and Path(project_path).exists():
            self.project_workspace.load_project_path(project_path)
        if self.project_workspace.active_group_id:
            workflow = self.workflow_workspace.current_workflow() if hasattr(self, 'workflow_workspace') else None
            if workflow is None:
                self.workspace_tabs.setCurrentIndex(self._workflow_tab_routes['workflow'])
            else:
                tab_index = int(state.get('current_tab', 0))
                if 0 <= tab_index < self.workspace_tabs.count() and self.workspace_tabs.isTabVisible(tab_index):
                    self.workspace_tabs.setCurrentIndex(tab_index)
                else:
                    self.workspace_tabs.setCurrentIndex(self._workflow_tab_routes['workflow'])
            return
        generation_state = state.get('generation_workspace')
        if isinstance(generation_state, dict):
            self.generation_workspace.apply_state(generation_state)
        chroma = state.get('chroma')
        if isinstance(chroma, dict):
            self.chroma_profiles.apply_profile_data(chroma, persist_last=False)
        alignment = state.get('alignment')
        if isinstance(alignment, dict):
            self.alignment_studio._apply_alignment_profile_data(alignment, persist_last=False)
        export_state = state.get('export')
        if isinstance(export_state, dict):
            r1_state = export_state.get('r1', export_state)
            if isinstance(r1_state, dict):
                self.format_combo.setCurrentIndex(int(r1_state.get('format_index', self.format_combo.currentIndex())))
                self.crop_checkbox.setChecked(bool(r1_state.get('crop_to_subject', self.crop_checkbox.isChecked())))
                self.padding_spin.setValue(int(r1_state.get('padding', self.padding_spin.value())))
            studio_state = export_state.get('studio')
            if isinstance(studio_state, dict):
                self.export_studio.apply_state(studio_state)
        last_sequence_manifest = state.get('last_sequence_manifest')
        last_video_path = state.get('last_video_path')
        if isinstance(last_sequence_manifest, str) and Path(last_sequence_manifest).exists() and not self.video.is_open:
            self._open_sequence_manifest_path(last_sequence_manifest, select_all=False)
        elif isinstance(last_video_path, str) and Path(last_video_path).exists() and not self.video.is_open:
            self._open_video_path(last_video_path)
            selection = state.get('selection')
            if isinstance(selection, dict):
                frames = selection.get('selected_frames')
                if isinstance(frames, list):
                    self.selected_frames = sorted(set(int(v) for v in frames if isinstance(v, int) or str(v).isdigit()))
                    self._refresh_selection_list()
                    self.cleanup_studio.set_selected_frames(self.selected_frames)
        tab_index = int(state.get('current_tab', 0))
        if 0 <= tab_index < self.workspace_tabs.count():
            self.workspace_tabs.setCurrentIndex(tab_index)

    @staticmethod
    def _format_time(seconds: float) -> str:
        milliseconds_total = max(0, int(round(seconds * 1000.0)))
        minutes, remainder = divmod(milliseconds_total, 60_000)
        whole_seconds, milliseconds = divmod(remainder, 1000)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f'{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}'
        return f'{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}'

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_playback()
        self.smart_studio.player.stop()
        if self.project_workspace.current_project_path is not None:
            try:
                self.project_workspace.update_project_snapshot(self._capture_project_snapshot())
                self._save_active_group_snapshot()
            except Exception:
                pass
        self._persist_application_state()
        self.generation_workspace.shutdown()
        self.video.close()
        super().closeEvent(event)
