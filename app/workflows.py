from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

WORKFLOW_VERSION = 'R5e10'

WORKFLOW_DEFINITIONS: dict[str, dict[str, Any]] = {
    'standard': {
        'title': 'Standard Workflow · Video → Sprite',
        'description': 'Ready WAN references → video generation → selection → clean-up → alignment → save settings → export.',
        'steps': [
            {'id': 'video_generation', 'title': 'WAN video generation', 'route': 'generation'},
            {'id': 'frame_selection', 'title': 'Frame selection', 'route': 'extraction'},
            {'id': 'cleanup', 'title': 'Clean-up / alpha mask', 'route': 'cleanup'},
            {'id': 'alignment', 'title': 'Frame alignment', 'route': 'alignment'},
            {'id': 'settings_checkpoint', 'title': 'Save settings', 'route': 'workflow'},
            {'id': 'export', 'title': 'Sprite sheet / image export', 'route': 'export'},
        ],
        'visible_routes': {
            'project', 'workflow', 'generation', 'extraction', 'cleanup', 'alignment',
            'smart_selection', 'export', 'production_presets', 'calibration', 'prompt_builder', 'character_set',
        },
    },
    'full': {
        'title': 'Full Workflow · AI → Motion Reference → Sprite',
        'description': 'Prompt image → motion spritesheet → reference video → final generation → selection → clean-up → alignment → save → export.',
        'steps': [
            {'id': 'image_generation', 'title': 'Image generation from prompt', 'route': 'image_generation'},
            {'id': 'spritesheet_import', 'title': 'Import and decompose motion spritesheet', 'route': 'spritesheet'},
            {'id': 'motion_reference', 'title': 'Generate and promote motion video', 'route': 'generation'},
            {'id': 'final_video_generation', 'title': 'Final video generation with image + motion', 'route': 'generation'},
            {'id': 'frame_selection', 'title': 'Frame selection', 'route': 'extraction'},
            {'id': 'cleanup', 'title': 'Clean-up / alpha mask', 'route': 'cleanup'},
            {'id': 'alignment', 'title': 'Frame alignment', 'route': 'alignment'},
            {'id': 'settings_checkpoint', 'title': 'Save settings', 'route': 'workflow'},
            {'id': 'export', 'title': 'Sprite sheet / image export', 'route': 'export'},
        ],
        'visible_routes': {
            'project', 'workflow', 'generation', 'extraction', 'cleanup', 'alignment',
            'smart_selection', 'export', 'production_presets', 'calibration', 'prompt_builder',
            'spritesheet', 'image_generation', 'character_set',
        },
    },
    'spritesheet_rework': {
        'title': 'Spritesheet Rework',
        'description': 'Import spritesheet → select/include-exclude frames → alpha/clean-up → scaling/alignment → save settings → re-export.',
        'steps': [
            {'id': 'spritesheet_import', 'title': 'Import and decompose spritesheet', 'route': 'spritesheet'},
            {'id': 'frame_selection', 'title': 'Frame selection / include-exclude', 'route': 'extraction'},
            {'id': 'cleanup', 'title': 'Alpha mask and clean-up', 'route': 'cleanup'},
            {'id': 'alignment', 'title': 'Scaling and alignment', 'route': 'alignment'},
            {'id': 'settings_checkpoint', 'title': 'Save settings', 'route': 'workflow'},
            {'id': 'export', 'title': 'Re-export spritesheet / images', 'route': 'export'},
        ],
        'visible_routes': {
            'project', 'workflow', 'extraction', 'cleanup', 'alignment', 'smart_selection',
            'export', 'production_presets', 'spritesheet', 'character_set',
        },
    },
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def workflow_definition(workflow_type: str) -> dict[str, Any]:
    if workflow_type not in WORKFLOW_DEFINITIONS:
        raise ValueError(f'Unsupported workflow: {workflow_type}')
    return deepcopy(WORKFLOW_DEFINITIONS[workflow_type])


def new_workflow_state(workflow_type: str) -> dict[str, Any]:
    workflow_definition(workflow_type)
    return {
        'version': WORKFLOW_VERSION,
        'type': workflow_type,
        'current_step': WORKFLOW_DEFINITIONS[workflow_type]['steps'][0]['id'],
        'completed_steps': [],
        'skipped_steps': [],
        'guided_tabs': False,
        'settings_checkpoints': [],
        'motion_reference': {},
        'created_at': now_iso(),
        'updated_at': now_iso(),
    }


def normalize_workflow_state(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    workflow_type = str(value.get('type') or '').strip()
    if workflow_type not in WORKFLOW_DEFINITIONS:
        return None
    result = new_workflow_state(workflow_type)
    result.update({k: deepcopy(v) for k, v in value.items() if k in result})
    valid_steps = {step['id'] for step in WORKFLOW_DEFINITIONS[workflow_type]['steps']}
    result['completed_steps'] = [str(v) for v in result.get('completed_steps', []) if str(v) in valid_steps]
    result['skipped_steps'] = [str(v) for v in result.get('skipped_steps', []) if str(v) in valid_steps]
    if str(result.get('current_step')) not in valid_steps:
        result['current_step'] = WORKFLOW_DEFINITIONS[workflow_type]['steps'][0]['id']
    if not isinstance(result.get('settings_checkpoints'), list):
        result['settings_checkpoints'] = []
    if not isinstance(result.get('motion_reference'), dict):
        result['motion_reference'] = {}
    result['guided_tabs'] = bool(result.get('guided_tabs', False))
    return result


def _path_key(value: Any) -> str:
    if not value:
        return ''
    try:
        return str(Path(str(value)).expanduser().resolve())
    except Exception:
        return str(value)


def inferred_completed_steps(group: dict[str, Any], workflow: dict[str, Any]) -> set[str]:
    assets = group.get('assets') if isinstance(group.get('assets'), dict) else {}
    pipeline = group.get('pipeline_state') if isinstance(group.get('pipeline_state'), dict) else {}
    metadata = group.get('metadata') if isinstance(group.get('metadata'), dict) else {}
    completed = set(str(v) for v in workflow.get('completed_steps', []))

    workflow_type = workflow.get('type')
    if workflow_type == 'standard':
        if assets.get('source_video'):
            completed.add('video_generation')
    elif workflow_type == 'full':
        if assets.get('generated_image'):
            completed.add('image_generation')
        if assets.get('source_sequence_manifest') or assets.get('source_spritesheet'):
            completed.add('spritesheet_import')
        motion = workflow.get('motion_reference') if isinstance(workflow.get('motion_reference'), dict) else {}
        if assets.get('motion_reference') and motion.get('promoted_from_source_video'):
            completed.add('motion_reference')
        promoted_source = _path_key(motion.get('promoted_from_source_video'))
        current_source = _path_key(assets.get('source_video'))
        if 'motion_reference' in completed and current_source and promoted_source and current_source != promoted_source:
            completed.add('final_video_generation')
    elif workflow_type == 'spritesheet_rework':
        if assets.get('source_sequence_manifest') or assets.get('source_spritesheet'):
            completed.add('spritesheet_import')

    selection = pipeline.get('selection') if isinstance(pipeline.get('selection'), dict) else {}
    if selection.get('selected_frames'):
        completed.add('frame_selection')
    cleanup = pipeline.get('cleanup') if isinstance(pipeline.get('cleanup'), dict) else {}
    if cleanup.get('frame_indices'):
        completed.add('cleanup')
    alignment = pipeline.get('alignment') if isinstance(pipeline.get('alignment'), dict) else {}
    if alignment.get('frame_states'):
        completed.add('alignment')
    if workflow.get('settings_checkpoints'):
        completed.add('settings_checkpoint')
    if group.get('exports') or str(group.get('status')) in {'exported', 'complete'}:
        completed.add('export')

    # Preserve any explicit workflow metadata kept by older/newer builds.
    stored = metadata.get('workflow') if isinstance(metadata.get('workflow'), dict) else {}
    if stored is not workflow:
        completed.update(str(v) for v in stored.get('completed_steps', []) if isinstance(v, str))
    return completed


def step_statuses(group: dict[str, Any], workflow: dict[str, Any]) -> list[dict[str, Any]]:
    definition = workflow_definition(str(workflow['type']))
    completed = inferred_completed_steps(group, workflow)
    skipped = set(str(v) for v in workflow.get('skipped_steps', []))
    current = str(workflow.get('current_step') or '')
    rows: list[dict[str, Any]] = []
    for index, step in enumerate(definition['steps']):
        status = 'pending'
        if step['id'] in skipped:
            status = 'skipped'
        elif step['id'] in completed:
            status = 'complete'
        elif step['id'] == current:
            status = 'current'
        rows.append({**step, 'index': index, 'status': status})
    return rows


def next_incomplete_step(group: dict[str, Any], workflow: dict[str, Any]) -> str | None:
    for row in step_statuses(group, workflow):
        if row['status'] not in {'complete', 'skipped'}:
            return str(row['id'])
    return None


def set_step_state(workflow: dict[str, Any], step_id: str, state: str) -> dict[str, Any]:
    result = normalize_workflow_state(workflow)
    if result is None:
        raise ValueError('Invalid workflow.')
    valid = {step['id'] for step in WORKFLOW_DEFINITIONS[result['type']]['steps']}
    if step_id not in valid:
        raise ValueError(f'Invalid step: {step_id}')
    completed = set(result.get('completed_steps', []))
    skipped = set(result.get('skipped_steps', []))
    completed.discard(step_id)
    skipped.discard(step_id)
    if state == 'complete':
        completed.add(step_id)
    elif state == 'skipped':
        skipped.add(step_id)
    elif state != 'pending':
        raise ValueError(f'Unsupported step state: {state}')
    result['completed_steps'] = list(completed)
    result['skipped_steps'] = list(skipped)
    result['updated_at'] = now_iso()
    return result
