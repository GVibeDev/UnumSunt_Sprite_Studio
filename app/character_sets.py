from __future__ import annotations

import json
import shutil
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

CHARACTER_SET_VERSION = 'R5e11'
DIRECTIONS = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')
LAYER_KINDS = ('base', 'outfit', 'equipment', 'accessory', 'effect', 'custom')
SUPPORTED_LAYER_EXTENSIONS = {'.png', '.webp'}


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def new_character_set_state() -> dict[str, Any]:
    return {
        'version': CHARACTER_SET_VERSION,
        'layers': [],
        'notes': '',
        'created_at': now_iso(),
        'updated_at': now_iso(),
    }


def normalize_character_set_state(value: Any) -> dict[str, Any]:
    result = new_character_set_state()
    if not isinstance(value, dict):
        return result
    result['notes'] = str(value.get('notes') or '')
    result['created_at'] = str(value.get('created_at') or result['created_at'])
    layers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value.get('layers', []) if isinstance(value.get('layers'), list) else []):
        if not isinstance(raw, dict):
            continue
        layer_id = str(raw.get('id') or f'layer_{uuid.uuid4().hex[:10]}')
        if layer_id in seen:
            layer_id = f'layer_{uuid.uuid4().hex[:10]}'
        seen.add(layer_id)
        kind = str(raw.get('kind') or 'custom').lower()
        if kind not in LAYER_KINDS:
            kind = 'custom'
        opacity = float(raw.get('opacity', 1.0))
        layers.append({
            'id': layer_id,
            'name': str(raw.get('name') or f'Layer {index + 1}'),
            'kind': kind,
            'enabled': bool(raw.get('enabled', True)),
            'export_enabled': bool(raw.get('export_enabled', True)),
            'opacity': max(0.0, min(1.0, opacity)),
            'order': index,
            'notes': str(raw.get('notes') or ''),
        })
    result['layers'] = layers
    result['version'] = CHARACTER_SET_VERSION
    result['updated_at'] = str(value.get('updated_at') or result['updated_at'])
    return result


def add_layer(state: dict[str, Any], name: str, *, kind: str = 'custom') -> tuple[dict[str, Any], dict[str, Any]]:
    result = normalize_character_set_state(state)
    normalized_name = str(name).strip()
    if not normalized_name:
        raise ValueError('The layer name cannot be empty.')
    kind = str(kind).lower()
    if kind not in LAYER_KINDS:
        raise ValueError(f'Unsupported layer type: {kind}')
    layer = {
        'id': f'layer_{uuid.uuid4().hex[:10]}',
        'name': normalized_name,
        'kind': kind,
        'enabled': True,
        'export_enabled': True,
        'opacity': 1.0,
        'order': len(result['layers']),
        'notes': '',
    }
    result['layers'].append(layer)
    result['updated_at'] = now_iso()
    return result, deepcopy(layer)


def update_layer(state: dict[str, Any], layer_id: str, **changes: Any) -> dict[str, Any]:
    result = normalize_character_set_state(state)
    for layer in result['layers']:
        if layer['id'] != layer_id:
            continue
        if 'name' in changes:
            name = str(changes['name']).strip()
            if not name:
                raise ValueError('The layer name cannot be empty.')
            layer['name'] = name
        if 'kind' in changes:
            kind = str(changes['kind']).lower()
            if kind not in LAYER_KINDS:
                raise ValueError(f'Unsupported layer type: {kind}')
            layer['kind'] = kind
        for key in ('enabled', 'export_enabled'):
            if key in changes:
                layer[key] = bool(changes[key])
        if 'opacity' in changes:
            layer['opacity'] = max(0.0, min(1.0, float(changes['opacity'])))
        if 'notes' in changes:
            layer['notes'] = str(changes['notes'])
        result['updated_at'] = now_iso()
        return result
    raise KeyError(layer_id)


def remove_layer(state: dict[str, Any], layer_id: str) -> dict[str, Any]:
    result = normalize_character_set_state(state)
    before = len(result['layers'])
    result['layers'] = [layer for layer in result['layers'] if layer['id'] != layer_id]
    if len(result['layers']) == before:
        raise KeyError(layer_id)
    for index, layer in enumerate(result['layers']):
        layer['order'] = index
    result['updated_at'] = now_iso()
    return result


def move_layer(state: dict[str, Any], layer_id: str, delta: int) -> dict[str, Any]:
    result = normalize_character_set_state(state)
    index = next((i for i, layer in enumerate(result['layers']) if layer['id'] == layer_id), None)
    if index is None:
        raise KeyError(layer_id)
    target = max(0, min(len(result['layers']) - 1, index + int(delta)))
    if target != index:
        layer = result['layers'].pop(index)
        result['layers'].insert(target, layer)
    for order, layer in enumerate(result['layers']):
        layer['order'] = order
    result['updated_at'] = now_iso()
    return result


def character_set_coverage(groups: list[dict[str, Any]], subject_id: str) -> dict[str, Any]:
    by_id = {str(group.get('id')): group for group in groups if isinstance(group, dict)}
    subject = by_id.get(str(subject_id))
    if subject is None or subject.get('type') != 'subject':
        raise KeyError(subject_id)
    animations = [g for g in groups if g.get('type') == 'animation' and g.get('parent_id') == subject_id]
    animations.sort(key=lambda g: str(g.get('name', '')).lower())
    rows: list[dict[str, Any]] = []
    total_slots = len(animations) * len(DIRECTIONS)
    present = 0
    ready = 0
    for animation in animations:
        directions = [g for g in groups if g.get('type') == 'direction' and g.get('parent_id') == animation.get('id')]
        by_direction: dict[str, dict[str, Any]] = {}
        for group in directions:
            direction = str((group.get('metadata') or {}).get('direction') or group.get('name') or '').upper()
            if direction in DIRECTIONS:
                by_direction[direction] = group
        cells = []
        for direction in DIRECTIONS:
            group = by_direction.get(direction)
            if group is None:
                cells.append({'direction': direction, 'group_id': None, 'status': 'missing', 'present': False})
                continue
            present += 1
            status = str(group.get('status') or 'missing')
            if status in {'aligned', 'exported', 'complete'}:
                ready += 1
            cells.append({'direction': direction, 'group_id': str(group.get('id')), 'status': status, 'present': True})
        rows.append({'animation_id': str(animation.get('id')), 'animation': str(animation.get('name')), 'directions': cells})
    return {
        'subject_id': subject_id,
        'subject': str(subject.get('name')),
        'rows': rows,
        'animation_count': len(animations),
        'total_slots': total_slots,
        'present_slots': present,
        'ready_slots': ready,
        'coverage_percent': (100.0 * present / total_slots) if total_slots else 0.0,
        'ready_percent': (100.0 * ready / total_slots) if total_slots else 0.0,
    }


def inspect_layer_source(source: Path) -> dict[str, Any]:
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(source)
    files: list[Path]
    mode: str
    if source.is_file():
        if source.suffix.lower() not in SUPPORTED_LAYER_EXTENSIONS:
            raise ValueError('Raster layers support PNG or WebP.')
        files = [source]
        mode = 'single'
    elif source.is_dir():
        files = sorted(
            path for path in source.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_LAYER_EXTENSIONS
        )
        if not files:
            raise ValueError('The folder contains no PNG/WebP frames.')
        mode = 'sequence'
    else:
        raise ValueError('Invalid layer source.')

    expected: tuple[int, int] | None = None
    has_alpha = True
    for path in files:
        with Image.open(path) as image:
            size = tuple(image.size)
            if expected is None:
                expected = size
            elif size != expected:
                raise ValueError('The layer frames do not all have the same dimensions.')
            has_alpha = has_alpha and ('A' in image.getbands() or image.info.get('transparency') is not None)
    assert expected is not None
    return {
        'mode': mode,
        'files': [str(path.resolve()) for path in files],
        'frame_count': len(files),
        'width': int(expected[0]),
        'height': int(expected[1]),
        'has_alpha': bool(has_alpha),
    }


def copy_layer_source(source: Path, target_dir: Path, *, layer_id: str) -> dict[str, Any]:
    info = inspect_layer_source(source)
    target_dir = Path(target_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for index, raw in enumerate(info['files']):
        path = Path(raw)
        suffix = path.suffix.lower()
        name = f'frame_{index:06d}{suffix}' if info['mode'] == 'sequence' else f'layer{suffix}'
        target = target_dir / name
        shutil.copy2(path, target)
        copied.append(str(target.resolve()))
    manifest = {
        'version': CHARACTER_SET_VERSION,
        'layer_id': str(layer_id),
        'mode': info['mode'],
        'frame_count': info['frame_count'],
        'width': info['width'],
        'height': info['height'],
        'has_alpha': info['has_alpha'],
        'files': copied,
        'imported_at': now_iso(),
    }
    manifest_path = target_dir / 'layer_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    manifest['manifest_path'] = str(manifest_path.resolve())
    return manifest


def normalize_direction_layer_stack(value: Any) -> dict[str, Any]:
    result = {'version': CHARACTER_SET_VERSION, 'assignments': {}, 'updated_at': now_iso()}
    if not isinstance(value, dict):
        return result
    raw_assignments = value.get('assignments') if isinstance(value.get('assignments'), dict) else {}
    for layer_id, raw in raw_assignments.items():
        if not isinstance(raw, dict):
            continue
        result['assignments'][str(layer_id)] = {
            'manifest_path': str(raw.get('manifest_path') or ''),
            'mode': str(raw.get('mode') or 'single'),
            'frame_count': max(1, int(raw.get('frame_count') or 1)),
            'width': max(0, int(raw.get('width') or 0)),
            'height': max(0, int(raw.get('height') or 0)),
            'has_alpha': bool(raw.get('has_alpha', False)),
            'offset_x': int(raw.get('offset_x') or 0),
            'offset_y': int(raw.get('offset_y') or 0),
            'visible': bool(raw.get('visible', True)),
        }
    result['updated_at'] = str(value.get('updated_at') or result['updated_at'])
    return result


def layer_assignment_coverage(groups: list[dict[str, Any]], subject_id: str, layer_ids: list[str]) -> dict[str, Any]:
    animation_ids = {g['id'] for g in groups if g.get('type') == 'animation' and g.get('parent_id') == subject_id}
    directions = [g for g in groups if g.get('type') == 'direction' and g.get('parent_id') in animation_ids]
    totals = {layer_id: 0 for layer_id in layer_ids}
    for group in directions:
        metadata = group.get('metadata') if isinstance(group.get('metadata'), dict) else {}
        stack = normalize_direction_layer_stack(metadata.get('layer_stack'))
        for layer_id in layer_ids:
            assignment = stack['assignments'].get(layer_id)
            if assignment and assignment.get('manifest_path'):
                totals[layer_id] += 1
    return {
        'direction_count': len(directions),
        'assigned_by_layer': totals,
    }
