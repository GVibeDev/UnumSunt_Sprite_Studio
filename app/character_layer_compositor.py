from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image


class CharacterLayerCompositeError(ValueError):
    """Raised when a Character Set layer stack cannot be composed safely."""


def _require_rgba(frame: np.ndarray, *, label: str) -> np.ndarray:
    array = np.asarray(frame)
    if array.ndim != 3 or array.shape[2] != 4 or array.dtype != np.uint8:
        raise CharacterLayerCompositeError(f'{label} must be RGBA uint8 H×W×4.')
    return np.ascontiguousarray(array)


def _load_manifest(assignment: dict[str, Any], *, layer_name: str) -> tuple[dict[str, Any], list[Path]]:
    manifest_path = Path(str(assignment.get('manifest_path') or '')).expanduser()
    if not manifest_path:
        raise CharacterLayerCompositeError(f'Layer "{layer_name}" has no manifest path.')
    if not manifest_path.is_file():
        raise CharacterLayerCompositeError(
            f'Layer "{layer_name}" manifest is missing: {manifest_path}'
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise CharacterLayerCompositeError(
            f'Layer "{layer_name}" manifest cannot be read: {manifest_path}'
        ) from exc
    if not isinstance(manifest, dict):
        raise CharacterLayerCompositeError(f'Layer "{layer_name}" manifest is invalid.')
    raw_files = manifest.get('files')
    if not isinstance(raw_files, list) or not raw_files:
        raise CharacterLayerCompositeError(f'Layer "{layer_name}" manifest contains no frames.')
    files = [Path(str(raw)).expanduser() for raw in raw_files]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise CharacterLayerCompositeError(
            f'Layer "{layer_name}" is missing {len(missing)} raster file(s): {missing[0]}'
        )
    declared_count = int(manifest.get('frame_count') or len(files))
    if declared_count != len(files):
        raise CharacterLayerCompositeError(
            f'Layer "{layer_name}" manifest frame_count={declared_count} but contains {len(files)} files.'
        )
    return manifest, files


def _load_layer_frames(assignment: dict[str, Any], *, layer_name: str) -> list[np.ndarray]:
    manifest, files = _load_manifest(assignment, layer_name=layer_name)
    frames: list[np.ndarray] = []
    expected_size: tuple[int, int] | None = None
    for path in files:
        try:
            with Image.open(path) as image:
                rgba = np.asarray(image.convert('RGBA'), dtype=np.uint8)
        except Exception as exc:
            raise CharacterLayerCompositeError(
                f'Layer "{layer_name}" frame cannot be decoded: {path}'
            ) from exc
        frame = np.ascontiguousarray(rgba)
        size = (frame.shape[1], frame.shape[0])
        if expected_size is None:
            expected_size = size
        elif size != expected_size:
            raise CharacterLayerCompositeError(
                f'Layer "{layer_name}" contains inconsistent frame dimensions.'
            )
        frames.append(frame)

    assert expected_size is not None
    declared_width = int(assignment.get('width') or manifest.get('width') or expected_size[0])
    declared_height = int(assignment.get('height') or manifest.get('height') or expected_size[1])
    if expected_size != (declared_width, declared_height):
        raise CharacterLayerCompositeError(
            f'Layer "{layer_name}" declares {declared_width}×{declared_height} but raster data is '
            f'{expected_size[0]}×{expected_size[1]}.'
        )
    return frames


def _alpha_composite_at(base: np.ndarray, overlay: np.ndarray, *, offset_x: int, offset_y: int, opacity: float) -> np.ndarray:
    result = _require_rgba(base, label='Base frame').copy()
    layer = _require_rgba(overlay, label='Layer frame')

    base_h, base_w = result.shape[:2]
    layer_h, layer_w = layer.shape[:2]
    left = max(0, int(offset_x))
    top = max(0, int(offset_y))
    right = min(base_w, int(offset_x) + layer_w)
    bottom = min(base_h, int(offset_y) + layer_h)
    if left >= right or top >= bottom:
        return result

    src_left = left - int(offset_x)
    src_top = top - int(offset_y)
    src = layer[src_top:src_top + (bottom - top), src_left:src_left + (right - left)].astype(np.float32) / 255.0
    dst = result[top:bottom, left:right].astype(np.float32) / 255.0

    alpha_scale = max(0.0, min(1.0, float(opacity)))
    src_a = src[:, :, 3:4] * alpha_scale
    dst_a = dst[:, :, 3:4]
    out_a = src_a + dst_a * (1.0 - src_a)

    src_premul = src[:, :, :3] * src_a
    dst_premul = dst[:, :, :3] * dst_a
    out_premul = src_premul + dst_premul * (1.0 - src_a)
    out_rgb = np.zeros_like(out_premul)
    nonzero = out_a[:, :, 0] > 1e-8
    out_rgb[nonzero] = out_premul[nonzero] / out_a[nonzero]

    combined = np.concatenate((out_rgb, out_a), axis=2)
    result[top:bottom, left:right] = np.clip(np.rint(combined * 255.0), 0, 255).astype(np.uint8)
    return result


def compose_character_layers(
    base_frames: Iterable[np.ndarray],
    *,
    character_set: dict[str, Any],
    direction_stack: dict[str, Any],
    for_export: bool,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Composite the active Direction layer stack over prepared base frames.

    Single-image assignments are reused for every base frame. Sequence assignments
    must contain exactly the same number of frames as the base animation. The
    compositor never cycles/truncates a mismatched sequence because doing so would
    silently corrupt animation timing.
    """

    bases = [_require_rgba(frame, label=f'Base frame {index}') for index, frame in enumerate(base_frames)]
    if not bases:
        raise CharacterLayerCompositeError('No base frames are available for Character Set compositing.')
    base_shape = bases[0].shape
    if any(frame.shape != base_shape for frame in bases[1:]):
        raise CharacterLayerCompositeError('Character Set compositing requires base frames with identical dimensions.')

    layers = character_set.get('layers') if isinstance(character_set, dict) else None
    assignments = direction_stack.get('assignments') if isinstance(direction_stack, dict) else None
    if not isinstance(layers, list) or not isinstance(assignments, dict):
        raise CharacterLayerCompositeError('Character Set layer metadata is invalid.')

    ordered_layers = sorted(
        (layer for layer in layers if isinstance(layer, dict)),
        key=lambda layer: int(layer.get('order') or 0),
    )
    prepared: list[tuple[dict[str, Any], dict[str, Any], list[np.ndarray]]] = []
    skipped: list[str] = []

    for layer in ordered_layers:
        layer_id = str(layer.get('id') or '')
        layer_name = str(layer.get('name') or layer_id or 'Unnamed layer')
        if not layer_id:
            raise CharacterLayerCompositeError('Character Set contains a layer without an id.')
        if not bool(layer.get('enabled', True)):
            skipped.append(f'{layer_name}: disabled')
            continue
        if for_export and not bool(layer.get('export_enabled', True)):
            skipped.append(f'{layer_name}: export disabled')
            continue
        assignment = assignments.get(layer_id)
        if not isinstance(assignment, dict) or not assignment.get('manifest_path'):
            skipped.append(f'{layer_name}: no assignment')
            continue
        if not bool(assignment.get('visible', True)):
            skipped.append(f'{layer_name}: hidden')
            continue

        layer_frames = _load_layer_frames(assignment, layer_name=layer_name)
        mode = str(assignment.get('mode') or 'single').strip().lower()
        if mode == 'single':
            if len(layer_frames) != 1:
                raise CharacterLayerCompositeError(
                    f'Layer "{layer_name}" is marked single but contains {len(layer_frames)} frames.'
                )
        elif mode == 'sequence':
            if len(layer_frames) != len(bases):
                raise CharacterLayerCompositeError(
                    f'Layer "{layer_name}" sequence has {len(layer_frames)} frames but the base animation has '
                    f'{len(bases)}. Assign a matching sequence before preview/export.'
                )
        else:
            raise CharacterLayerCompositeError(f'Layer "{layer_name}" uses unsupported assignment mode: {mode}')
        prepared.append((layer, assignment, layer_frames))

    result = [frame.copy() for frame in bases]
    applied_layers: list[dict[str, Any]] = []
    for layer, assignment, layer_frames in prepared:
        layer_name = str(layer.get('name') or layer.get('id'))
        opacity = max(0.0, min(1.0, float(layer.get('opacity', 1.0))))
        offset_x = int(assignment.get('offset_x') or 0)
        offset_y = int(assignment.get('offset_y') or 0)
        for index, base in enumerate(result):
            source = layer_frames[0] if len(layer_frames) == 1 else layer_frames[index]
            result[index] = _alpha_composite_at(
                base,
                source,
                offset_x=offset_x,
                offset_y=offset_y,
                opacity=opacity,
            )
        applied_layers.append({
            'id': str(layer.get('id')),
            'name': layer_name,
            'kind': str(layer.get('kind') or 'custom'),
            'mode': str(assignment.get('mode') or 'single'),
            'frame_count': len(layer_frames),
            'opacity': opacity,
            'offset_x': offset_x,
            'offset_y': offset_y,
        })

    return result, {
        'base_frame_count': len(bases),
        'applied_layer_count': len(applied_layers),
        'applied_layers': applied_layers,
        'skipped_layers': skipped,
        'for_export': bool(for_export),
    }
