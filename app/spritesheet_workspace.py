from __future__ import annotations

from pathlib import Path
from typing import Callable
import json

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.project_store import ProjectStore
from app.spritesheet_import import (
    AtlasRegion,
    GridSliceSettings,
    auto_detect_regular_grid,
    create_reference_sheet,
    detect_atlas_regions,
    extract_atlas_frames,
    load_image_rgba,
    normalize_frames_to_canvas,
    save_rgba_png,
    save_sequence_manifest,
    slice_regular_sheet,
)


class SpriteSheetWorkspace(QWidget):
    sequence_ready = Signal(object)
    reference_sheet_ready = Signal(str)
    status_message = Signal(str)

    def __init__(
        self,
        *,
        project_store_provider: Callable[[], ProjectStore | None],
        active_group_id_provider: Callable[[], str | None],
    ) -> None:
        super().__init__()
        self._project_store_provider = project_store_provider
        self._active_group_id_provider = active_group_id_provider
        self._source_path: Path | None = None
        self._source_rgba: np.ndarray | None = None
        self._frames: list[np.ndarray] = []
        self._source_indices: list[int] = []
        self._rectangles: list[tuple[int, int, int, int]] = []
        self._atlas_regions: list[AtlasRegion] = []
        self._extraction_payload: dict = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        intro = QLabel(
            'Importa spritesheet esistenti, decomponili in frame e riusa la pipeline R1/R2/R3/R4. '
            'La reference sheet WAN viene costruita da key pose esplicitamente selezionate.'
        )
        intro.setWordWrap(True)
        intro.setStyleSheet('QLabel { color: #f4f6f8; padding: 7px; background: #252b33; border: 1px solid #555; }')
        root.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 5, 0)
        self.preview_label = QLabel('Nessuno spritesheet caricato')
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(620, 520)
        self.preview_label.setStyleSheet('QLabel { color: #f4f6f8; background: #171a1f; border: 1px solid #41464f; }')
        left_layout.addWidget(self.preview_label, 1)

        self.frame_list = QListWidget()
        self.frame_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.frame_list.setFlow(QListWidget.Flow.LeftToRight)
        self.frame_list.setWrapping(True)
        self.frame_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.frame_list.setMinimumHeight(180)
        left_layout.addWidget(self.frame_list)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(5, 0, 0, 0)

        source_group = QGroupBox('Sorgente')
        source_form = QFormLayout(source_group)
        self.source_label = QLabel('—')
        self.source_label.setWordWrap(True)
        open_button = QPushButton('Apri spritesheet…')
        open_button.clicked.connect(self._open_sheet)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem('Griglia regolare', 'grid')
        self.mode_combo.addItem('Atlas irregolare · alpha components', 'atlas')
        self.mode_combo.currentIndexChanged.connect(self._update_mode_controls)
        source_form.addRow('', open_button)
        source_form.addRow('File', self.source_label)
        source_form.addRow('Modalità', self.mode_combo)
        right_layout.addWidget(source_group)

        grid_group = QGroupBox('Grid slicer')
        grid_form = QFormLayout(grid_group)
        self.frame_w_spin = QSpinBox(); self.frame_w_spin.setRange(1, 8192); self.frame_w_spin.setValue(96)
        self.frame_h_spin = QSpinBox(); self.frame_h_spin.setRange(1, 8192); self.frame_h_spin.setValue(96)
        self.rows_spin = QSpinBox(); self.rows_spin.setRange(1, 512); self.rows_spin.setValue(1)
        self.cols_spin = QSpinBox(); self.cols_spin.setRange(1, 512); self.cols_spin.setValue(1)
        self.hpad_spin = QSpinBox(); self.hpad_spin.setRange(0, 1024)
        self.vpad_spin = QSpinBox(); self.vpad_spin.setRange(0, 1024)
        self.margin_spin = QSpinBox(); self.margin_spin.setRange(0, 2048)
        self.order_combo = QComboBox(); self.order_combo.addItem('Righe → colonne', 'row_major'); self.order_combo.addItem('Colonne → righe', 'column_major')
        auto_button = QPushButton('Auto-detect griglia')
        auto_button.clicked.connect(self._auto_detect_grid)
        grid_form.addRow('Frame width', self.frame_w_spin)
        grid_form.addRow('Frame height', self.frame_h_spin)
        grid_form.addRow('Rows', self.rows_spin)
        grid_form.addRow('Columns', self.cols_spin)
        grid_form.addRow('Padding orizz.', self.hpad_spin)
        grid_form.addRow('Padding vert.', self.vpad_spin)
        grid_form.addRow('Outer margin', self.margin_spin)
        grid_form.addRow('Reading order', self.order_combo)
        grid_form.addRow('', auto_button)
        self.grid_group = grid_group
        right_layout.addWidget(grid_group)

        atlas_group = QGroupBox('Atlas irregolare')
        atlas_form = QFormLayout(atlas_group)
        self.atlas_min_area_spin = QSpinBox(); self.atlas_min_area_spin.setRange(1, 10000000); self.atlas_min_area_spin.setValue(8)
        self.atlas_alignment_combo = QComboBox()
        self.atlas_alignment_combo.addItem('Bottom center', 'bottom_center')
        self.atlas_alignment_combo.addItem('Center', 'center')
        self.atlas_alignment_combo.addItem('Top left', 'top_left')
        atlas_form.addRow('Area minima componente', self.atlas_min_area_spin)
        atlas_form.addRow('Normalizza canvas', self.atlas_alignment_combo)
        self.atlas_group = atlas_group
        right_layout.addWidget(atlas_group)

        extract_group = QGroupBox('Decompose')
        extract_form = QFormLayout(extract_group)
        self.extract_info = QLabel('Nessuna estrazione eseguita.')
        self.extract_info.setWordWrap(True)
        extract_button = QPushButton('Estrai / aggiorna preview frame')
        extract_button.clicked.connect(self._extract)
        select_all_button = QPushButton('Seleziona tutti i frame')
        select_all_button.clicked.connect(self._select_all_frames)
        extract_form.addRow('Stato', self.extract_info)
        extract_form.addRow('', extract_button)
        extract_form.addRow('', select_all_button)
        right_layout.addWidget(extract_group)

        import_group = QGroupBox('Pipeline esistente')
        import_form = QFormLayout(import_group)
        self.fps_spin = QSpinBox(); self.fps_spin.setRange(1, 120); self.fps_spin.setValue(12)
        import_all_button = QPushButton('Importa tutti nella pipeline')
        import_selected_button = QPushButton('Importa selezionati nella pipeline')
        import_all_button.clicked.connect(lambda: self._import_pipeline(selected_only=False))
        import_selected_button.clicked.connect(lambda: self._import_pipeline(selected_only=True))
        import_form.addRow('FPS timeline', self.fps_spin)
        import_form.addRow('', import_all_button)
        import_form.addRow('', import_selected_button)
        right_layout.addWidget(import_group)

        reference_group = QGroupBox('WAN Reference Sheet Builder')
        reference_form = QFormLayout(reference_group)
        self.reference_columns_spin = QSpinBox(); self.reference_columns_spin.setRange(1, 8); self.reference_columns_spin.setValue(4)
        self.reference_padding_spin = QSpinBox(); self.reference_padding_spin.setRange(0, 128); self.reference_padding_spin.setValue(8)
        reference_button = QPushButton('Crea reference sheet dai selezionati')
        reference_button.clicked.connect(self._create_reference_sheet)
        reference_form.addRow('Columns', self.reference_columns_spin)
        reference_form.addRow('Padding', self.reference_padding_spin)
        reference_form.addRow('', reference_button)
        right_layout.addWidget(reference_group)

        note = QLabel(
            'Nota: la detection automatica è sempre correggibile manualmente. Gli atlas irregolari vengono '
            'normalizzati su un canvas comune prima di entrare nella pipeline, perché R1/R2/R3 richiedono geometria stabile.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color: #9198a5;')
        right_layout.addWidget(note)
        right_layout.addStretch(1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1050, 430])
        root.addWidget(splitter, 1)
        self._update_mode_controls()

    @staticmethod
    def _pixmap_from_rgba(rgba: np.ndarray, max_w: int = 900, max_h: int = 650) -> QPixmap:
        arr = np.ascontiguousarray(rgba)
        image = QImage(arr.data, arr.shape[1], arr.shape[0], arr.strides[0], QImage.Format.Format_RGBA8888).copy()
        pixmap = QPixmap.fromImage(image)
        return pixmap.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)

    def _open_sheet(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            'Apri spritesheet',
            '',
            'Immagini (*.png *.webp *.bmp *.tif *.tiff);;Tutti i file (*)',
        )
        if not path:
            return
        try:
            rgba = load_image_rgba(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Errore spritesheet', str(exc))
            return
        self._source_path = Path(path).resolve()
        self._source_rgba = rgba
        self._frames = []
        self._source_indices = []
        self._rectangles = []
        self._atlas_regions = []
        self._extraction_payload = {}
        self.frame_list.clear()
        self.source_label.setText(self._source_path.name)
        self.source_label.setToolTip(str(self._source_path))
        self.preview_label.setPixmap(self._pixmap_from_rgba(rgba))
        self.extract_info.setText(f'Sorgente {rgba.shape[1]}×{rgba.shape[0]} caricata. Configura o usa Auto-detect.')
        self.frame_w_spin.setMaximum(rgba.shape[1])
        self.frame_h_spin.setMaximum(rgba.shape[0])
        self.frame_w_spin.setValue(min(self.frame_w_spin.value(), rgba.shape[1]))
        self.frame_h_spin.setValue(min(self.frame_h_spin.value(), rgba.shape[0]))
        self.status_message.emit(f'Spritesheet aperto: {self._source_path.name}')

    def _update_mode_controls(self, *_args) -> None:
        grid = str(self.mode_combo.currentData()) == 'grid'
        self.grid_group.setEnabled(grid)
        self.atlas_group.setEnabled(not grid)

    def _auto_detect_grid(self) -> None:
        if self._source_rgba is None:
            return
        try:
            result = auto_detect_regular_grid(self._source_rgba)
        except Exception as exc:
            QMessageBox.warning(self, 'Auto-detection', str(exc))
            return
        s = result.settings
        self.frame_w_spin.setValue(s.frame_width)
        self.frame_h_spin.setValue(s.frame_height)
        self.rows_spin.setValue(s.rows)
        self.cols_spin.setValue(s.columns)
        self.hpad_spin.setValue(s.horizontal_padding)
        self.vpad_spin.setValue(s.vertical_padding)
        self.margin_spin.setValue(s.outer_margin)
        index = self.order_combo.findData(s.reading_order)
        if index >= 0:
            self.order_combo.setCurrentIndex(index)
        self.extract_info.setText(f'Auto-detect: confidenza {result.confidence}. {result.reason} Valori modificabili manualmente.')
        self.status_message.emit(f'Auto-detect griglia: {result.confidence}.')

    def _grid_settings(self) -> GridSliceSettings:
        return GridSliceSettings(
            frame_width=self.frame_w_spin.value(),
            frame_height=self.frame_h_spin.value(),
            rows=self.rows_spin.value(),
            columns=self.cols_spin.value(),
            horizontal_padding=self.hpad_spin.value(),
            vertical_padding=self.vpad_spin.value(),
            outer_margin=self.margin_spin.value(),
            reading_order=str(self.order_combo.currentData()),
        )

    def _extract(self) -> None:
        if self._source_rgba is None or self._source_path is None:
            QMessageBox.information(self, 'Nessuna sorgente', 'Aprire prima uno spritesheet.')
            return
        try:
            if str(self.mode_combo.currentData()) == 'grid':
                settings = self._grid_settings().normalized()
                frames, rects = slice_regular_sheet(self._source_rgba, settings)
                self._frames = frames
                self._rectangles = rects
                self._atlas_regions = []
                self._source_indices = list(range(len(frames)))
                self._extraction_payload = {
                    'mode': 'grid',
                    'grid': settings.to_dict(),
                    'rectangles': [list(rect) for rect in rects],
                }
                self.extract_info.setText(f'Griglia estratta: {len(frames)} frame da {settings.columns}×{settings.rows}.')
            else:
                regions = detect_atlas_regions(self._source_rgba, min_area=self.atlas_min_area_spin.value())
                if not regions:
                    raise ValueError('Nessuna componente atlas rilevata. Per immagini opache usare Grid slicer o preparare alpha.')
                raw_frames = extract_atlas_frames(self._source_rgba, regions)
                frames, canvas, offsets = normalize_frames_to_canvas(
                    raw_frames,
                    alignment=str(self.atlas_alignment_combo.currentData()),
                )
                self._frames = frames
                self._atlas_regions = regions
                self._rectangles = [(r.x, r.y, r.width, r.height) for r in regions]
                self._source_indices = list(range(len(frames)))
                self._extraction_payload = {
                    'mode': 'atlas_alpha_components',
                    'regions': [region.to_dict() for region in regions],
                    'normalization': {
                        'alignment': str(self.atlas_alignment_combo.currentData()),
                        'canvas_width': canvas[0],
                        'canvas_height': canvas[1],
                        'offsets': [list(value) for value in offsets],
                    },
                }
                self.extract_info.setText(f'Atlas estratto: {len(frames)} componenti; canvas comune {canvas[0]}×{canvas[1]}.')
        except Exception as exc:
            QMessageBox.warning(self, 'Decompose non riuscito', str(exc))
            return
        self._refresh_frame_list()
        self.status_message.emit(f'Decompose completato: {len(self._frames)} frame.')

    def _refresh_frame_list(self) -> None:
        self.frame_list.clear()
        for index, frame in enumerate(self._frames):
            item = QListWidgetItem(f'F{index:03d} · {frame.shape[1]}×{frame.shape[0]}')
            item.setData(Qt.ItemDataRole.UserRole, index)
            thumb = self._pixmap_from_rgba(frame, 96, 96)
            item.setIcon(QIcon(thumb))
            self.frame_list.addItem(item)

    def _select_all_frames(self) -> None:
        for row in range(self.frame_list.count()):
            self.frame_list.item(row).setSelected(True)

    def _selected_indices(self) -> list[int]:
        values = [int(item.data(Qt.ItemDataRole.UserRole)) for item in self.frame_list.selectedItems()]
        return sorted(set(values))

    def _require_group_workspace(self) -> tuple[ProjectStore, str, Path] | None:
        store = self._project_store_provider()
        group_id = self._active_group_id_provider()
        if store is None or not group_id:
            QMessageBox.information(
                self,
                'Project Group richiesto',
                'Per importare una sequenza persistente è necessario un Project Group attivo.',
            )
            return None
        return store, group_id, store.group_workspace(group_id)

    def _save_sequence(self, indices: list[int]) -> dict | None:
        if not indices or not self._frames or self._source_path is None:
            QMessageBox.information(self, 'Nessun frame', 'Eseguire Decompose e scegliere almeno un frame.')
            return None
        context = self._require_group_workspace()
        if context is None:
            return None
        _store, group_id, workspace = context
        import_root = workspace / 'spritesheet_import'
        frames_dir = import_root / 'frames'
        frames_dir.mkdir(parents=True, exist_ok=True)
        # Deterministic rewrite of the active imported sequence only.
        for old in frames_dir.glob('frame_*.png'):
            old.unlink()
        saved_paths: list[Path] = []
        source_indices: list[int] = []
        for output_index, source_index in enumerate(indices):
            frame = self._frames[source_index]
            target = frames_dir / f'frame_{output_index:04d}.png'
            save_rgba_png(target, frame)
            saved_paths.append(target)
            source_indices.append(source_index)
        extraction = dict(self._extraction_payload)
        extraction['imported_indices'] = source_indices
        manifest_path = save_sequence_manifest(
            import_root / 'import_manifest.json',
            source_sheet=self._source_path,
            frame_paths=saved_paths,
            fps=float(self.fps_spin.value()),
            extraction=extraction,
            source_indices=source_indices,
        )
        return {
            'group_id': group_id,
            'manifest_path': str(manifest_path),
            'frame_paths': [str(path) for path in saved_paths],
            'fps': float(self.fps_spin.value()),
            'source_sheet': str(self._source_path),
            'source_indices': source_indices,
        }

    def _import_pipeline(self, *, selected_only: bool) -> None:
        if not self._frames:
            QMessageBox.information(self, 'Nessun frame', 'Eseguire prima Decompose.')
            return
        indices = self._selected_indices() if selected_only else list(range(len(self._frames)))
        if selected_only and not indices:
            QMessageBox.information(self, 'Nessuna selezione', 'Selezionare i frame da importare.')
            return
        payload = self._save_sequence(indices)
        if payload is None:
            return
        self.sequence_ready.emit(payload)
        self.status_message.emit(f'Sequenza spritesheet pronta: {len(indices)} frame.')

    def _create_reference_sheet(self) -> None:
        if not self._frames or self._source_path is None:
            QMessageBox.information(self, 'Nessun frame', 'Eseguire prima Decompose.')
            return
        indices = self._selected_indices()
        if not indices:
            QMessageBox.information(self, 'Nessuna key pose', 'Selezionare i frame da usare nella reference sheet WAN.')
            return
        try:
            sheet, manifest = create_reference_sheet(
                self._frames,
                indices,
                columns=self.reference_columns_spin.value(),
                padding=self.reference_padding_spin.value(),
            )
        except Exception as exc:
            QMessageBox.warning(self, 'Reference sheet', str(exc))
            return

        context = self._require_group_workspace()
        if context is not None:
            _store, _group_id, workspace = context
            output_dir = workspace / 'spritesheet_import' / 'reference'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / 'wan_reference_sheet.png'
            manifest_path = output_dir / 'wan_reference_sheet.json'
        else:
            # Currently _require_group_workspace shows a message; keep a deterministic fallback for future reuse.
            return
        save_rgba_png(output_path, sheet)
        payload = dict(manifest)
        payload['source_sheet'] = str(self._source_path)
        manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        self.reference_sheet_ready.emit(str(output_path))
        self.status_message.emit(f'WAN Reference Sheet creata: {output_path.name}')
