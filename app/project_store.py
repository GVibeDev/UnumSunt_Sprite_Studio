from __future__ import annotations

import json
import shutil
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from app.performance_probe import perf_instrument
from app.character_sets import (
    add_layer as character_add_layer,
    copy_layer_source,
    move_layer as character_move_layer,
    new_character_set_state,
    normalize_character_set_state,
    normalize_direction_layer_stack,
    remove_layer as character_remove_layer,
    update_layer as character_update_layer,
)


PROJECT_FILENAME = 'unum_sunt_sprite_project.json'
GROUP_TYPES = ('subject', 'animation', 'direction')
GROUP_STATUSES = (
    'missing',
    'source_ready',
    'generated',
    'extracted',
    'selected',
    'cleaned',
    'aligned',
    'exported',
    'complete',
)
DIRECTIONS = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')


def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _empty_pipeline_state() -> dict[str, Any]:
    return {
        'generation': {},
        'image_generation': {},
        'chroma': {},
        'selection': {},
        'cleanup': {},
        'alignment': {},
        'export': {},
    }


def _empty_assets() -> dict[str, Any]:
    return {
        'reference_image': None,
        'generated_image': None,
        'image_generation_manifest': None,
        'motion_reference': None,
        'source_video': None,
        'source_sequence_manifest': None,
        'source_spritesheet': None,
    }




def _remap_workspace_paths(value: Any, source_workspace: Path, target_workspace: Path) -> Any:
    """Remap absolute paths that point inside a copied Project Group workspace."""
    source_root = source_workspace.resolve()
    target_root = target_workspace.resolve()
    if isinstance(value, dict):
        return {key: _remap_workspace_paths(item, source_root, target_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_remap_workspace_paths(item, source_root, target_root) for item in value]
    if isinstance(value, tuple):
        return tuple(_remap_workspace_paths(item, source_root, target_root) for item in value)
    if isinstance(value, str):
        try:
            candidate = Path(value)
            if not candidate.is_absolute():
                return value
            resolved = candidate.resolve()
            relative = resolved.relative_to(source_root)
            return str((target_root / relative).resolve())
        except Exception:
            return value
    return value

def _default_project_payload(name: str, subject: str = '', notes: str = '') -> dict[str, Any]:
    timestamp = _now()
    return {
        'version': 'R5c3',
        'name': name,
        'subject': subject,
        'notes': notes,
        'created_at': timestamp,
        'updated_at': timestamp,
        'assets': _empty_assets(),
        'pipeline_state': _empty_pipeline_state(),
        'jobs': [],
        'groups': [],
        'active_group_id': None,
    }


def _normalize_group(group: dict[str, Any]) -> dict[str, Any]:
    result = {
        'id': str(group.get('id') or f'grp_{uuid.uuid4().hex[:12]}'),
        'parent_id': group.get('parent_id'),
        'type': str(group.get('type') or 'direction'),
        'name': str(group.get('name') or 'Group'),
        'status': str(group.get('status') or 'missing'),
        'notes': str(group.get('notes') or ''),
        'created_at': str(group.get('created_at') or _now()),
        'updated_at': str(group.get('updated_at') or _now()),
        'workspace': str(group.get('workspace') or ''),
        'assets': _empty_assets(),
        'pipeline_state': _empty_pipeline_state(),
        'jobs': [],
        'exports': [],
        'metadata': {},
    }
    if result['type'] not in GROUP_TYPES:
        result['type'] = 'direction'
    if result['status'] not in GROUP_STATUSES:
        result['status'] = 'missing'
    if isinstance(group.get('assets'), dict):
        result['assets'].update(deepcopy(group['assets']))
    if isinstance(group.get('pipeline_state'), dict):
        for key in result['pipeline_state']:
            value = group['pipeline_state'].get(key)
            if isinstance(value, dict):
                result['pipeline_state'][key] = deepcopy(value)
    if isinstance(group.get('jobs'), list):
        result['jobs'] = deepcopy(group['jobs'])
    if isinstance(group.get('exports'), list):
        result['exports'] = deepcopy(group['exports'])
    if isinstance(group.get('metadata'), dict):
        result['metadata'] = deepcopy(group['metadata'])
    return result


class ProjectStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else None

    @staticmethod
    def project_file(project_dir: Path) -> Path:
        return Path(project_dir) / PROJECT_FILENAME

    @property
    def project_dir(self) -> Path:
        if self.path is None:
            raise FileNotFoundError('No project file configured.')
        return self.path.parent

    @classmethod
    def create(cls, project_dir: Path, *, name: str | None = None, subject: str = '', notes: str = '') -> 'ProjectStore':
        project_dir = Path(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        for folder in (
            'source', 'motion_references', 'generations', 'frames', 'cleanup', 'animations', 'exports', 'manifests', 'groups'
        ):
            (project_dir / folder).mkdir(exist_ok=True)
        project_name = (name or project_dir.name).strip() or project_dir.name
        store = cls(cls.project_file(project_dir))
        store.save(_default_project_payload(project_name, subject=subject, notes=notes))
        return store

    @classmethod
    def open(cls, project_dir_or_file: Path) -> 'ProjectStore':
        target = Path(project_dir_or_file)
        path = target if target.name == PROJECT_FILENAME else cls.project_file(target)
        if not path.exists():
            raise FileNotFoundError(f'Project file not found: {path}')
        return cls(path)

    @perf_instrument('project_store.load')
    def load(self) -> dict[str, Any]:
        if self.path is None or not self.path.exists():
            raise FileNotFoundError('No project file configured.')
        payload = json.loads(self.path.read_text(encoding='utf-8'))
        data = _default_project_payload(str(payload.get('name', self.path.parent.name)))
        if isinstance(payload, dict):
            for key in ('name', 'subject', 'notes', 'created_at', 'updated_at'):
                if key in payload:
                    data[key] = payload[key]
            # Loading an older project upgrades it in-memory to the current project schema.
            data['version'] = 'R5c3'
            if isinstance(payload.get('assets'), dict):
                data['assets'].update(deepcopy(payload['assets']))
            if isinstance(payload.get('pipeline_state'), dict):
                for key in data['pipeline_state']:
                    value = payload['pipeline_state'].get(key)
                    if isinstance(value, dict):
                        data['pipeline_state'][key] = deepcopy(value)
            if isinstance(payload.get('jobs'), list):
                data['jobs'] = deepcopy(payload['jobs'])
            if isinstance(payload.get('groups'), list):
                data['groups'] = [_normalize_group(group) for group in payload['groups'] if isinstance(group, dict)]
            active_group_id = payload.get('active_group_id')
            if isinstance(active_group_id, str) and any(g['id'] == active_group_id for g in data['groups']):
                data['active_group_id'] = active_group_id
        return data

    @perf_instrument('project_store.save')
    def save(self, payload: dict[str, Any]) -> None:
        if self.path is None:
            raise FileNotFoundError('No project file configured.')
        data = deepcopy(payload)
        data['version'] = 'R5c3'
        data['updated_at'] = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        (self.path.parent / 'groups').mkdir(exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    def update_pipeline_state(self, state: dict[str, Any]) -> None:
        payload = self.load()
        payload['pipeline_state'] = deepcopy(state)
        self.save(payload)

    def append_job(self, job_payload: dict[str, Any]) -> None:
        payload = self.load()
        payload.setdefault('jobs', []).append(deepcopy(job_payload))
        self.save(payload)

    # ---------------- Project Groups ----------------

    def list_groups(self) -> list[dict[str, Any]]:
        return deepcopy(self.load()['groups'])

    def get_group(self, group_id: str) -> dict[str, Any] | None:
        for group in self.load()['groups']:
            if group['id'] == group_id:
                return deepcopy(group)
        return None

    def get_active_group(self) -> dict[str, Any] | None:
        payload = self.load()
        active_id = payload.get('active_group_id')
        if not active_id:
            return None
        for group in payload['groups']:
            if group['id'] == active_id:
                return deepcopy(group)
        return None

    def _group_index(self, groups: list[dict[str, Any]], group_id: str) -> int:
        for index, group in enumerate(groups):
            if group['id'] == group_id:
                return index
        raise KeyError(f'Project group not found: {group_id}')

    def _validate_parent(self, groups: list[dict[str, Any]], parent_id: str | None, group_type: str) -> None:
        if group_type == 'subject':
            if parent_id is not None:
                raise ValueError('A subject group cannot have a parent.')
            return
        if parent_id is None:
            raise ValueError(f'A {group_type} group requires a parent.')
        parent = groups[self._group_index(groups, parent_id)]
        expected = 'subject' if group_type == 'animation' else 'animation'
        if parent['type'] != expected:
            raise ValueError(f'A {group_type} group must be inside a {expected} group.')

    def create_group(
        self,
        *,
        group_type: str,
        name: str,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        group_type = str(group_type).strip().lower()
        if group_type not in GROUP_TYPES:
            raise ValueError(f'Unsupported group type: {group_type}')
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError('The group name cannot be empty.')
        payload = self.load()
        groups = payload['groups']
        self._validate_parent(groups, parent_id, group_type)
        group_id = f'grp_{uuid.uuid4().hex[:12]}'
        group = _normalize_group({
            'id': group_id,
            'parent_id': parent_id,
            'type': group_type,
            'name': normalized_name,
            'status': 'missing',
            'metadata': metadata or {},
            'workspace': f'groups/{group_id}',
        })
        groups.append(group)
        workspace = self.project_dir / group['workspace']
        workspace.mkdir(parents=True, exist_ok=True)
        if group_type == 'direction':
            for folder in ('source', 'motion_references', 'generations', 'frames', 'cleanup', 'alignment', 'exports', 'manifests', 'layers'):
                (workspace / folder).mkdir(exist_ok=True)
        self.save(payload)
        return deepcopy(group)

    def update_group(
        self,
        group_id: str,
        *,
        name: str | None = None,
        status: str | None = None,
        notes: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        if name is not None:
            normalized_name = str(name).strip()
            if not normalized_name:
                raise ValueError('The group name cannot be empty.')
            group['name'] = normalized_name
        if status is not None:
            if status not in GROUP_STATUSES:
                raise ValueError(f'Unsupported group status: {status}')
            group['status'] = status
        if notes is not None:
            group['notes'] = str(notes)
        if metadata is not None:
            group['metadata'].update(deepcopy(metadata))
        group['updated_at'] = _now()
        self.save(payload)
        return deepcopy(group)

    def children_of(self, parent_id: str | None) -> list[dict[str, Any]]:
        return [g for g in self.list_groups() if g.get('parent_id') == parent_id]

    def group_lineage(self, group_id: str) -> list[dict[str, Any]]:
        groups = {group['id']: group for group in self.list_groups()}
        current = groups.get(group_id)
        if current is None:
            raise KeyError(f'Project group not found: {group_id}')
        lineage: list[dict[str, Any]] = []
        seen: set[str] = set()
        while current is not None:
            if current['id'] in seen:
                raise ValueError('Cycle detected in project groups.')
            seen.add(current['id'])
            lineage.append(current)
            parent_id = current.get('parent_id')
            current = groups.get(parent_id) if parent_id else None
        lineage.reverse()
        return deepcopy(lineage)

    def group_label(self, group_id: str) -> str:
        return ' / '.join(group['name'] for group in self.group_lineage(group_id))

    def set_active_group(self, group_id: str | None) -> None:
        payload = self.load()
        if group_id is not None:
            index = self._group_index(payload['groups'], group_id)
            if payload['groups'][index]['type'] != 'direction':
                raise ValueError('Only a direction group can become the active production context.')
        payload['active_group_id'] = group_id
        self.save(payload)

    def update_group_snapshot(self, group_id: str, snapshot: dict[str, Any]) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        assets = snapshot.get('assets')
        if isinstance(assets, dict):
            group['assets'].update(deepcopy(assets))
        pipeline = snapshot.get('pipeline_state')
        if isinstance(pipeline, dict):
            for key in group['pipeline_state']:
                value = pipeline.get(key)
                if isinstance(value, dict):
                    group['pipeline_state'][key] = deepcopy(value)
        # Never downgrade a manually/automatically advanced production state.
        observed = 'missing'
        if group['assets'].get('reference_image') or group['assets'].get('motion_reference'):
            observed = 'source_ready'
        if group['assets'].get('source_video') or group['assets'].get('source_sequence_manifest'):
            observed = 'generated'
        selection = group['pipeline_state'].get('selection', {})
        if isinstance(selection, dict) and selection.get('selected_frames'):
            observed = 'selected'
        cleanup = group['pipeline_state'].get('cleanup', {})
        if isinstance(cleanup, dict) and cleanup.get('frame_indices'):
            observed = 'cleaned'
        alignment = group['pipeline_state'].get('alignment', {})
        if isinstance(alignment, dict) and alignment.get('frame_states'):
            observed = 'aligned'
        current_rank = GROUP_STATUSES.index(group['status']) if group['status'] in GROUP_STATUSES else 0
        observed_rank = GROUP_STATUSES.index(observed)
        if observed_rank > current_rank:
            group['status'] = observed
        group['updated_at'] = _now()
        self.save(payload)

    def append_group_job(self, group_id: str, job_payload: dict[str, Any]) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        group['jobs'].append(deepcopy(job_payload))
        group['updated_at'] = _now()
        result = job_payload.get('result') if isinstance(job_payload, dict) else None
        if isinstance(result, dict) and result.get('state') == 'completed' and result.get('video_path'):
            group['assets']['source_video'] = result['video_path']
            # A newly completed generation becomes the active frame source for this group.
            group['assets']['source_sequence_manifest'] = None
            group['assets']['source_spritesheet'] = None
            group['status'] = 'generated'
        self.save(payload)

    def append_group_export(self, group_id: str, export_payload: dict[str, Any]) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        group['exports'].append(deepcopy(export_payload))
        group['status'] = 'exported'
        group['updated_at'] = _now()
        self.save(payload)



    def get_group_workflow(self, group_id: str) -> dict[str, Any] | None:
        group = self.get_group(group_id)
        if group is None:
            raise KeyError(group_id)
        metadata = group.get('metadata') if isinstance(group.get('metadata'), dict) else {}
        workflow = metadata.get('workflow')
        return deepcopy(workflow) if isinstance(workflow, dict) else None

    def set_group_workflow(self, group_id: str, workflow: dict[str, Any]) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        group.setdefault('metadata', {})['workflow'] = deepcopy(workflow)
        group['updated_at'] = _now()
        self.save(payload)

    def clear_group_workflow(self, group_id: str) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        group.setdefault('metadata', {}).pop('workflow', None)
        group['updated_at'] = _now()
        self.save(payload)

    # ---------------- Character Set / Layer Manager R5e11 ----------------

    def subject_for_group(self, group_id: str) -> dict[str, Any]:
        lineage = self.group_lineage(group_id)
        subject = next((group for group in lineage if group.get('type') == 'subject'), None)
        if subject is None:
            raise ValueError('Il gruppo non appartiene a un soggetto.')
        return deepcopy(subject)

    def get_character_set(self, subject_id: str) -> dict[str, Any]:
        group = self.get_group(subject_id)
        if group is None or group.get('type') != 'subject':
            raise ValueError('Character Set disponibile solo su un gruppo Soggetto.')
        metadata = group.get('metadata') if isinstance(group.get('metadata'), dict) else {}
        return normalize_character_set_state(metadata.get('character_set'))

    def set_character_set(self, subject_id: str, state: dict[str, Any]) -> None:
        group = self.get_group(subject_id)
        if group is None or group.get('type') != 'subject':
            raise ValueError('Character Set disponibile solo su un gruppo Soggetto.')
        normalized = normalize_character_set_state(state)
        self.update_group(subject_id, metadata={'character_set': normalized})

    def add_character_layer(self, subject_id: str, name: str, *, kind: str = 'custom') -> dict[str, Any]:
        state = self.get_character_set(subject_id)
        state, layer = character_add_layer(state, name, kind=kind)
        self.set_character_set(subject_id, state)
        return layer

    def update_character_layer(self, subject_id: str, layer_id: str, **changes: Any) -> dict[str, Any]:
        state = character_update_layer(self.get_character_set(subject_id), layer_id, **changes)
        self.set_character_set(subject_id, state)
        return next(deepcopy(layer) for layer in state['layers'] if layer['id'] == layer_id)

    def move_character_layer(self, subject_id: str, layer_id: str, delta: int) -> None:
        state = character_move_layer(self.get_character_set(subject_id), layer_id, delta)
        self.set_character_set(subject_id, state)

    def remove_character_layer(self, subject_id: str, layer_id: str) -> None:
        state = character_remove_layer(self.get_character_set(subject_id), layer_id)
        payload = self.load()
        subject_index = self._group_index(payload['groups'], subject_id)
        payload['groups'][subject_index].setdefault('metadata', {})['character_set'] = state
        animation_ids = {
            group['id'] for group in payload['groups']
            if group.get('type') == 'animation' and group.get('parent_id') == subject_id
        }
        affected: list[Path] = []
        for group in payload['groups']:
            if group.get('type') != 'direction' or group.get('parent_id') not in animation_ids:
                continue
            metadata = group.setdefault('metadata', {})
            stack = normalize_direction_layer_stack(metadata.get('layer_stack'))
            stack['assignments'].pop(layer_id, None)
            stack['updated_at'] = _now()
            metadata['layer_stack'] = stack
            workspace = self.project_dir / str(group.get('workspace') or f"groups/{group['id']}")
            affected.append(workspace / 'layers' / layer_id)
        self.save(payload)
        for path in affected:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)

    def get_direction_layer_stack(self, group_id: str) -> dict[str, Any]:
        group = self.get_group(group_id)
        if group is None or group.get('type') != 'direction':
            raise ValueError('Lo stack layer è disponibile solo su una direzione.')
        metadata = group.get('metadata') if isinstance(group.get('metadata'), dict) else {}
        return normalize_direction_layer_stack(metadata.get('layer_stack'))

    def set_direction_layer_stack(self, group_id: str, stack: dict[str, Any]) -> None:
        group = self.get_group(group_id)
        if group is None or group.get('type') != 'direction':
            raise ValueError('Lo stack layer è disponibile solo su una direzione.')
        normalized = normalize_direction_layer_stack(stack)
        self.update_group(group_id, metadata={'layer_stack': normalized})

    def import_direction_layer_asset(self, group_id: str, layer_id: str, source: Path) -> dict[str, Any]:
        group = self.get_group(group_id)
        if group is None or group.get('type') != 'direction':
            raise ValueError('Assegnare layer soltanto a un gruppo Direzione.')
        subject = self.subject_for_group(group_id)
        state = self.get_character_set(subject['id'])
        if not any(layer['id'] == layer_id for layer in state['layers']):
            raise KeyError(f'Layer non appartenente al soggetto: {layer_id}')
        target = self.group_workspace(group_id) / 'layers' / layer_id
        manifest = copy_layer_source(Path(source), target, layer_id=layer_id)
        stack = self.get_direction_layer_stack(group_id)
        stack['assignments'][layer_id] = {
            'manifest_path': manifest['manifest_path'],
            'mode': manifest['mode'],
            'frame_count': manifest['frame_count'],
            'width': manifest['width'],
            'height': manifest['height'],
            'has_alpha': manifest['has_alpha'],
            'offset_x': 0,
            'offset_y': 0,
            'visible': True,
        }
        stack['updated_at'] = _now()
        self.set_direction_layer_stack(group_id, stack)
        return deepcopy(stack['assignments'][layer_id])

    def update_direction_layer_assignment(self, group_id: str, layer_id: str, **changes: Any) -> dict[str, Any]:
        stack = self.get_direction_layer_stack(group_id)
        assignment = stack['assignments'].get(layer_id)
        if not isinstance(assignment, dict):
            raise KeyError(layer_id)
        if 'offset_x' in changes:
            assignment['offset_x'] = int(changes['offset_x'])
        if 'offset_y' in changes:
            assignment['offset_y'] = int(changes['offset_y'])
        if 'visible' in changes:
            assignment['visible'] = bool(changes['visible'])
        stack['updated_at'] = _now()
        self.set_direction_layer_stack(group_id, stack)
        return deepcopy(assignment)

    def remove_direction_layer_asset(self, group_id: str, layer_id: str) -> None:
        stack = self.get_direction_layer_stack(group_id)
        stack['assignments'].pop(layer_id, None)
        stack['updated_at'] = _now()
        self.set_direction_layer_stack(group_id, stack)
        target = self.group_workspace(group_id) / 'layers' / layer_id
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    def get_group_calibration(self, group_id: str) -> dict[str, Any]:
        group = self.get_group(group_id)
        if group is None:
            raise KeyError(group_id)
        metadata = group.get('metadata') if isinstance(group.get('metadata'), dict) else {}
        calibration = metadata.get('calibration') if isinstance(metadata.get('calibration'), dict) else {}
        return deepcopy(calibration)

    def set_group_calibration(self, group_id: str, calibration: dict[str, Any]) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        group.setdefault('metadata', {})['calibration'] = deepcopy(calibration)
        group['updated_at'] = _now()
        self.save(payload)

    def update_group_calibration_run(self, group_id: str, run_id: str, run_payload: dict[str, Any]) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        metadata = group.setdefault('metadata', {})
        calibration = metadata.setdefault('calibration', {'runs': [], 'baseline_run_id': None})
        runs = calibration.setdefault('runs', [])
        for run_index, run in enumerate(runs):
            if isinstance(run, dict) and str(run.get('id')) == str(run_id):
                runs[run_index] = deepcopy(run_payload)
                break
        else:
            runs.append(deepcopy(run_payload))
        calibration['updated_at'] = _now()
        group['updated_at'] = _now()
        self.save(payload)

    def copy_group_data(self, source_group_id: str, target_group_id: str) -> None:
        if source_group_id == target_group_id:
            return
        payload = self.load()
        source_index = self._group_index(payload['groups'], source_group_id)
        target_index = self._group_index(payload['groups'], target_group_id)
        source = payload['groups'][source_index]
        target = payload['groups'][target_index]
        if source['type'] != 'direction' or target['type'] != 'direction':
            raise ValueError('Production data can only be copied between direction groups.')
        for key in ('assets', 'pipeline_state', 'jobs', 'exports'):
            target[key] = deepcopy(source[key])
        source_metadata = source.get('metadata') if isinstance(source.get('metadata'), dict) else {}
        if isinstance(source_metadata.get('layer_stack'), dict):
            target.setdefault('metadata', {})['layer_stack'] = deepcopy(source_metadata['layer_stack'])
        target['status'] = source['status']
        target['updated_at'] = _now()
        source_workspace = self.project_dir / str(source.get('workspace') or f"groups/{source_group_id}")
        target_workspace = self.project_dir / str(target.get('workspace') or f"groups/{target_group_id}")
        if target_workspace.exists():
            shutil.rmtree(target_workspace, ignore_errors=True)
        if source_workspace.exists():
            shutil.copytree(source_workspace, target_workspace, dirs_exist_ok=True)
        else:
            target_workspace.mkdir(parents=True, exist_ok=True)
        for folder in ('source', 'motion_references', 'generations', 'frames', 'cleanup', 'alignment', 'exports', 'manifests', 'layers'):
            (target_workspace / folder).mkdir(exist_ok=True)
        payload['groups'][target_index] = _remap_workspace_paths(target, source_workspace, target_workspace)
        self.save(payload)

    def duplicate_group(self, group_id: str) -> dict[str, Any]:
        payload = self.load()
        source_index = self._group_index(payload['groups'], group_id)
        source = payload['groups'][source_index]
        groups_by_parent: dict[str | None, list[dict[str, Any]]] = {}
        for group in payload['groups']:
            groups_by_parent.setdefault(group.get('parent_id'), []).append(group)

        created: list[dict[str, Any]] = []

        def clone_subtree(group: dict[str, Any], new_parent_id: str | None, root: bool) -> dict[str, Any]:
            new_id = f'grp_{uuid.uuid4().hex[:12]}'
            clone = deepcopy(group)
            clone['id'] = new_id
            clone['parent_id'] = new_parent_id
            clone['name'] = f"{group['name']} copy" if root else group['name']
            clone['created_at'] = _now()
            clone['updated_at'] = clone['created_at']
            source_workspace = self.project_dir / str(group.get('workspace') or f"groups/{group['id']}")
            clone['workspace'] = f'groups/{new_id}'
            created.append(clone)
            workspace = self.project_dir / clone['workspace']
            if source_workspace.exists():
                shutil.copytree(source_workspace, workspace, dirs_exist_ok=True)
            else:
                workspace.mkdir(parents=True, exist_ok=True)
            if clone['type'] == 'direction':
                for folder in ('source', 'motion_references', 'generations', 'frames', 'cleanup', 'alignment', 'exports', 'manifests', 'layers'):
                    (workspace / folder).mkdir(exist_ok=True)
            clone = _remap_workspace_paths(clone, source_workspace, workspace)
            created[-1] = clone
            for child in groups_by_parent.get(group['id'], []):
                clone_subtree(child, new_id, False)
            return clone

        root_clone = clone_subtree(source, source.get('parent_id'), True)
        payload['groups'].extend(created)
        self.save(payload)
        return deepcopy(root_clone)

    def delete_group(self, group_id: str) -> None:
        payload = self.load()
        groups = payload['groups']
        self._group_index(groups, group_id)
        to_delete = {group_id}
        changed = True
        while changed:
            changed = False
            for group in groups:
                if group.get('parent_id') in to_delete and group['id'] not in to_delete:
                    to_delete.add(group['id'])
                    changed = True
        workspaces = [group.get('workspace') for group in groups if group['id'] in to_delete]
        payload['groups'] = [group for group in groups if group['id'] not in to_delete]
        if payload.get('active_group_id') in to_delete:
            payload['active_group_id'] = None
        self.save(payload)
        for workspace in workspaces:
            if workspace:
                target = (self.project_dir / str(workspace)).resolve()
                groups_root = (self.project_dir / 'groups').resolve()
                if groups_root in target.parents and target.exists():
                    shutil.rmtree(target, ignore_errors=True)

    def assign_production_preset(self, group_id: str, preset_name: str, *, sections: list[str] | None = None) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        group['metadata']['production_preset'] = {
            'name': str(preset_name),
            'sections': list(sections or []),
            'applied_at': _now(),
        }
        group['updated_at'] = _now()
        self.save(payload)

    def clear_production_preset_assignment(self, group_id: str) -> None:
        payload = self.load()
        index = self._group_index(payload['groups'], group_id)
        group = payload['groups'][index]
        group['metadata'].pop('production_preset', None)
        group['updated_at'] = _now()
        self.save(payload)

    def group_workspace(self, group_id: str) -> Path:
        group = self.get_group(group_id)
        if group is None:
            raise KeyError(f'Project group not found: {group_id}')
        workspace = group.get('workspace') or f'groups/{group_id}'
        path = self.project_dir / str(workspace)
        path.mkdir(parents=True, exist_ok=True)
        return path
