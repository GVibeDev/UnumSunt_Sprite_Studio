from __future__ import annotations

from typing import Any, Callable

from app.character_layer_compositor import CharacterLayerCompositeError, compose_character_layers


class CharacterSetCompositeController:
    """Bridge Character Set metadata to the existing R2 renderer and shared canvas.

    The controller deliberately owns no project state. It reads the active Direction,
    asks the existing AlignmentStudio for prepared R2 frames, and composes a
    presentation/export copy of those frames. Base frames remain untouched.
    """

    def __init__(
        self,
        *,
        project_store_provider: Callable[[], Any | None],
        active_group_id_provider: Callable[[], str | None],
        aligned_payload_provider: Callable[[], dict],
        current_frame_index_provider: Callable[[], int],
        canvas_frame_setter: Callable[[Any, Any | None], None],
        show_canvas: Callable[[], None],
        status_callback: Callable[[str], None],
        warning_callback: Callable[[str, str], None],
        info_callback: Callable[[str, str], None],
    ) -> None:
        self._project_store_provider = project_store_provider
        self._active_group_id_provider = active_group_id_provider
        self._aligned_payload_provider = aligned_payload_provider
        self._current_frame_index_provider = current_frame_index_provider
        self._canvas_frame_setter = canvas_frame_setter
        self._show_canvas = show_canvas
        self._status_callback = status_callback
        self._warning_callback = warning_callback
        self._info_callback = info_callback

    def _context_for_direction(self, direction_id: str) -> tuple[Any, dict, dict, dict]:
        store = self._project_store_provider()
        if store is None:
            raise RuntimeError('Open a project before using Character Set layers.')
        direction = store.get_group(direction_id)
        if direction is None or direction.get('type') != 'direction':
            raise RuntimeError('Character Set compositing requires an existing Direction group.')
        subject = store.subject_for_group(direction_id)
        character_set = store.get_character_set(subject['id'])
        direction_stack = store.get_direction_layer_stack(direction_id)
        return store, direction, character_set, direction_stack

    def compose_payload(self, direction_id: str, *, for_export: bool) -> dict:
        active_group_id = self._active_group_id_provider()
        if str(active_group_id or '') != str(direction_id):
            raise RuntimeError(
                'The selected Character Set direction is not the active project Direction. '
                'Activate that direction first so the base R2 frames and layer stack cannot be mixed across directions.'
            )
        store, _direction, character_set, direction_stack = self._context_for_direction(direction_id)
        base_payload = self._aligned_payload_provider()
        base_frames = base_payload.get('rgba_frames')
        if not isinstance(base_frames, list) or not base_frames:
            raise RuntimeError('The active Direction has no prepared R2 frames for Character Set compositing.')
        composed, report = compose_character_layers(
            base_frames,
            character_set=character_set,
            direction_stack=direction_stack,
            for_export=for_export,
        )
        subject = store.subject_for_group(direction_id)
        metadata = dict(base_payload.get('metadata') or {})
        metadata['character_set'] = {
            'subject_id': str(subject['id']),
            'direction_group_id': str(direction_id),
            'direction_label': str(store.group_label(direction_id)),
            **report,
        }
        return {
            **base_payload,
            'rgba_frames': composed,
            'default_base_name': f"{base_payload.get('default_base_name', 'animation')}-character-set",
            'metadata': metadata,
        }

    def build_export_payload(self) -> dict:
        direction_id = self._active_group_id_provider()
        if not direction_id:
            raise RuntimeError('Activate a Direction group before exporting a Character Set composite.')
        return self.compose_payload(str(direction_id), for_export=True)

    def preview_direction(self, direction_id: str) -> None:
        try:
            payload = self.compose_payload(str(direction_id), for_export=False)
        except (RuntimeError, CharacterLayerCompositeError, ValueError, OSError) as exc:
            self._warning_callback('Character Set Preview', str(exc))
            return
        frames = payload.get('rgba_frames')
        if not isinstance(frames, list) or not frames:
            self._info_callback('Character Set Preview', 'No composite frames are available.')
            return
        metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
        selected_indices = metadata.get('selected_frame_indices') if isinstance(metadata, dict) else None
        preview_position = 0
        current_frame_index = int(self._current_frame_index_provider())
        if isinstance(selected_indices, list) and current_frame_index in selected_indices:
            preview_position = selected_indices.index(current_frame_index)
        preview_position = max(0, min(preview_position, len(frames) - 1))
        self._canvas_frame_setter(frames[preview_position], None)
        self._show_canvas()
        report = metadata.get('character_set') if isinstance(metadata, dict) else None
        layer_count = int(report.get('applied_layer_count') or 0) if isinstance(report, dict) else 0
        self._status_callback(
            f'Character Set preview: {layer_count} visible layer(s) composited on '
            f'frame {preview_position + 1}/{len(frames)}.'
        )
