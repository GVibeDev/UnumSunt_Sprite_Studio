from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable

from app.profile_store import ProfilesStore


PRESET_SCHEMA = 'unum-sunt-production-preset-v1'
PRESET_SECTIONS = ('generation', 'chroma', 'selection', 'alignment', 'export')


def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def normalize_sections(sections: Iterable[str] | None) -> list[str]:
    if sections is None:
        return list(PRESET_SECTIONS)
    result: list[str] = []
    for section in sections:
        key = str(section).strip().lower()
        if key in PRESET_SECTIONS and key not in result:
            result.append(key)
    return result


def sanitize_pipeline_state_for_preset(pipeline_state: dict[str, Any], sections: Iterable[str] | None = None) -> dict[str, Any]:
    """Extract reusable settings only; never copy per-group assets, frame selections, cleanup or machine paths."""
    selected = normalize_sections(sections)
    source = pipeline_state if isinstance(pipeline_state, dict) else {}
    result: dict[str, Any] = {}

    if 'generation' in selected:
        generation = source.get('generation')
        if isinstance(generation, dict):
            profile = generation.get('generation_profile')
            if isinstance(profile, dict):
                clean = deepcopy(profile)
                # File inputs belong to the group, not to a reusable production preset.
                clean.pop('reference_image', None)
                clean.pop('motion_video', None)
                result['generation'] = {'generation_profile': clean}

    if 'chroma' in selected:
        chroma = source.get('chroma')
        if isinstance(chroma, dict) and chroma:
            result['chroma'] = deepcopy(chroma)

    if 'selection' in selected:
        selection = source.get('selection')
        if isinstance(selection, dict):
            smart = selection.get('smart_selection')
            if isinstance(smart, dict):
                clean_smart = deepcopy(smart)
                for key in ('r1_selection', 'start_frame', 'end_frame'):
                    clean_smart.pop(key, None)
                result['selection'] = {'smart_selection': clean_smart}

    if 'alignment' in selected:
        alignment = source.get('alignment')
        if isinstance(alignment, dict):
            profile = alignment.get('profile', alignment)
            if isinstance(profile, dict) and profile:
                result['alignment'] = {'profile': deepcopy(profile)}

    if 'export' in selected:
        export = source.get('export')
        if isinstance(export, dict) and export:
            result['export'] = deepcopy(export)

    return result


def merge_preset_into_pipeline(current_pipeline: dict[str, Any], preset: dict[str, Any], sections: Iterable[str] | None = None) -> dict[str, Any]:
    """Merge preset settings while preserving group-specific runtime/session data."""
    result = deepcopy(current_pipeline) if isinstance(current_pipeline, dict) else {}
    selected = normalize_sections(sections if sections is not None else preset.get('sections'))
    preset_pipeline = preset.get('pipeline_state') if isinstance(preset, dict) else None
    if not isinstance(preset_pipeline, dict):
        return result

    if 'generation' in selected and isinstance(preset_pipeline.get('generation'), dict):
        current_generation = result.setdefault('generation', {})
        if not isinstance(current_generation, dict):
            current_generation = {}
            result['generation'] = current_generation
        incoming = preset_pipeline['generation']
        profile = incoming.get('generation_profile')
        if isinstance(profile, dict):
            existing_profile = current_generation.get('generation_profile')
            merged_profile = deepcopy(existing_profile) if isinstance(existing_profile, dict) else {}
            merged_profile.update(deepcopy(profile))
            current_generation['generation_profile'] = merged_profile

    if 'chroma' in selected and isinstance(preset_pipeline.get('chroma'), dict):
        result['chroma'] = deepcopy(preset_pipeline['chroma'])

    if 'selection' in selected and isinstance(preset_pipeline.get('selection'), dict):
        current_selection = result.setdefault('selection', {})
        if not isinstance(current_selection, dict):
            current_selection = {}
            result['selection'] = current_selection
        incoming_smart = preset_pipeline['selection'].get('smart_selection')
        if isinstance(incoming_smart, dict):
            existing_smart = current_selection.get('smart_selection')
            merged_smart = deepcopy(existing_smart) if isinstance(existing_smart, dict) else {}
            merged_smart.update(deepcopy(incoming_smart))
            current_selection['smart_selection'] = merged_smart
        # selected_frames remains untouched.

    if 'alignment' in selected and isinstance(preset_pipeline.get('alignment'), dict):
        current_alignment = result.setdefault('alignment', {})
        if not isinstance(current_alignment, dict):
            current_alignment = {}
            result['alignment'] = current_alignment
        incoming_profile = preset_pipeline['alignment'].get('profile')
        if isinstance(incoming_profile, dict):
            existing_profile = current_alignment.get('profile')
            merged_profile = deepcopy(existing_profile) if isinstance(existing_profile, dict) else {}
            merged_profile.update(deepcopy(incoming_profile))
            current_alignment['profile'] = merged_profile
        # frame_states and selected_indices remain untouched.

    if 'export' in selected and isinstance(preset_pipeline.get('export'), dict):
        existing_export = result.get('export')
        merged_export = deepcopy(existing_export) if isinstance(existing_export, dict) else {}
        for key, value in preset_pipeline['export'].items():
            if isinstance(value, dict) and isinstance(merged_export.get(key), dict):
                nested = deepcopy(merged_export[key])
                nested.update(deepcopy(value))
                merged_export[key] = nested
            else:
                merged_export[key] = deepcopy(value)
        result['export'] = merged_export

    return result


def build_production_preset(
    *,
    name: str,
    description: str,
    pipeline_state: dict[str, Any],
    sections: Iterable[str] | None = None,
    builtin: bool = False,
    calibration_required: bool = False,
    tags: Iterable[str] | None = None,
) -> dict[str, Any]:
    selected = normalize_sections(sections)
    sanitized = sanitize_pipeline_state_for_preset(pipeline_state, selected)
    actual_sections = [section for section in selected if section in sanitized]
    timestamp = _now()
    return {
        'schema': PRESET_SCHEMA,
        'application_version': 'R5c6a',
        'name': str(name).strip() or 'Production preset',
        'description': str(description).strip(),
        'sections': actual_sections,
        'pipeline_state': sanitized,
        'builtin': bool(builtin),
        'calibration_required': bool(calibration_required),
        'tags': [str(tag).strip() for tag in (tags or []) if str(tag).strip()],
        'created_at': timestamp,
        'updated_at': timestamp,
    }


def _starter_alignment(width: int, height: int, animation_name: str | None = None) -> dict[str, Any]:
    profile: dict[str, Any] = {
        'output_size_preset': f'square-{width}' if width == height and width in {36, 48, 64, 80, 96, 128, 160, 192, 224, 256} else 'custom',
        'lock_aspect_ratio': True,
        'preserve_pivot_proportion': True,
        'auto_fit_on_resize': True,
        'canvas_width': width,
        'canvas_height': height,
        'canvas_pivot_x': width / 2.0,
        'canvas_pivot_y': height * (88.0 / 96.0),
        'margin': max(1, round(width * 4 / 96)),
        'anchor_mode': 'ground',
        'loop': True,
    }
    if animation_name:
        profile['animation_name'] = animation_name
    return {'profile': profile}


def _starter_export() -> dict[str, Any]:
    return {
        'r1': {'format_index': 0, 'crop_to_subject': True, 'padding': 8},
        'studio': {
            'source_mode': 'aligned',
            'base_name': 'animation',
            'output_format_index': 0,
            'include_frames': True,
            'include_sheet': True,
            'sheet_layout_index': 1,
            'sheet_columns': 8,
            'sheet_padding': 0,
            'scale_factor': 1,
            'background_mode': 'transparent',
            'background_rgb': [0, 0, 0],
        },
    }


def starter_presets() -> dict[str, dict[str, Any]]:
    specs = (
        ('Starter · Walk · 96×96', 'Struttura Walk 96×96 + export PNG trasparente in griglia. I parametri WAN non sono impostati: calibrazione richiesta.', 96, 96, 'walk', ['walk', '96x96']),
        ('Starter · Idle · 96×96', 'Struttura Idle 96×96 + export PNG trasparente in griglia. I parametri WAN non sono impostati: calibrazione richiesta.', 96, 96, 'idle', ['idle', '96x96']),
        ('Starter · Small · 48×48', 'Output 48×48 con auto-fit + export PNG trasparente. Nessun parametro generativo viene imposto.', 48, 48, None, ['small', '48x48']),
        ('Starter · Small · 36×36', 'Output 36×36 con auto-fit + export PNG trasparente. Nessun parametro generativo viene imposto.', 36, 36, None, ['small', '36x36']),
        ('Starter · PNG Transparent Grid', 'Solo preset di export: frame + sprite sheet PNG trasparente in griglia.', 0, 0, None, ['export', 'png', 'transparent']),
    )
    result: dict[str, dict[str, Any]] = {}
    for name, description, width, height, animation, tags in specs:
        pipeline: dict[str, Any] = {'export': _starter_export()}
        sections = ['export']
        if width and height:
            pipeline['alignment'] = _starter_alignment(width, height, animation)
            sections.insert(0, 'alignment')
        preset = {
            'schema': PRESET_SCHEMA,
            'application_version': 'R5c6a',
            'name': name,
            'description': description,
            'sections': sections,
            'pipeline_state': pipeline,
            'builtin': True,
            'calibration_required': bool(width and height),
            'tags': tags,
            'created_at': 'builtin',
            'updated_at': 'builtin',
        }
        result[name] = preset
    return result


class ProductionPresetStore:
    def __init__(self, profiles_store: ProfilesStore | None = None) -> None:
        self.profiles_store = profiles_store or ProfilesStore()
        self.ensure_starters()

    def ensure_starters(self) -> None:
        for name, preset in starter_presets().items():
            existing = self.profiles_store.get_profile('pipeline', name)
            if existing is None or existing.get('builtin') is True:
                self.profiles_store.set_profile('pipeline', name, preset)

    def list_names(self) -> list[str]:
        return self.profiles_store.list_profiles('pipeline')

    def get(self, name: str) -> dict[str, Any] | None:
        return self.profiles_store.get_profile('pipeline', name)

    def save(self, name: str, preset: dict[str, Any]) -> None:
        clean = deepcopy(preset)
        clean['name'] = name
        clean['updated_at'] = _now()
        clean['builtin'] = False
        self.profiles_store.set_profile('pipeline', name, clean)

    def delete(self, name: str) -> None:
        preset = self.get(name)
        if preset and preset.get('builtin'):
            raise ValueError('I preset Starter integrati non possono essere eliminati.')
        self.profiles_store.delete_profile('pipeline', name)

    def duplicate(self, source_name: str, target_name: str) -> dict[str, Any]:
        preset = self.get(source_name)
        if preset is None:
            raise KeyError(source_name)
        copy = deepcopy(preset)
        copy['name'] = target_name
        copy['builtin'] = False
        copy['created_at'] = _now()
        copy['updated_at'] = copy['created_at']
        self.profiles_store.set_profile('pipeline', target_name, copy)
        return copy
