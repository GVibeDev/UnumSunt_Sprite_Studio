from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import uuid
from typing import Any, Iterable

from app.version import APP_VERSION


CALIBRATION_SCHEMA = 'unum-sunt-calibration-lab-v1'
CALIBRATION_RUN_SCHEMA = 'unum-sunt-calibration-run-v1'
CALIBRATION_VERDICTS = ('unrated', 'reject', 'usable', 'preferred')
VARIANT_FIELDS = (
    'steps',
    'frames',
    'fps',
    'seed',
    'resolution_class',
    'aspect_ratio',
    'positive_prompt',
    'negative_prompt',
)


def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def empty_calibration_state() -> dict[str, Any]:
    return {
        'schema': CALIBRATION_SCHEMA,
        'application_version': APP_VERSION,
        'baseline_run_id': None,
        'runs': [],
        'updated_at': _now(),
    }


def normalize_calibration_state(value: dict[str, Any] | None) -> dict[str, Any]:
    result = empty_calibration_state()
    if not isinstance(value, dict):
        return result
    baseline = value.get('baseline_run_id')
    if isinstance(baseline, str) or baseline is None:
        result['baseline_run_id'] = baseline
    runs = value.get('runs')
    if isinstance(runs, list):
        result['runs'] = [normalize_calibration_run(run) for run in runs if isinstance(run, dict)]
    result['updated_at'] = str(value.get('updated_at') or result['updated_at'])
    known = {run['id'] for run in result['runs']}
    if result['baseline_run_id'] not in known:
        result['baseline_run_id'] = None
    return result


def normalize_calibration_run(run: dict[str, Any]) -> dict[str, Any]:
    evaluation = run.get('evaluation') if isinstance(run.get('evaluation'), dict) else {}
    result = run.get('result') if isinstance(run.get('result'), dict) else {}
    profile = run.get('generation_profile') if isinstance(run.get('generation_profile'), dict) else {}
    environment = run.get('environment') if isinstance(run.get('environment'), dict) else {}
    return {
        'schema': CALIBRATION_RUN_SCHEMA,
        'id': str(run.get('id') or f'cal_{uuid.uuid4().hex[:12]}'),
        'source_kind': str(run.get('source_kind') or 'manual_snapshot'),
        'source_job_id': run.get('source_job_id') if isinstance(run.get('source_job_id'), str) else None,
        'created_at': str(run.get('created_at') or _now()),
        'generation_profile': deepcopy(profile),
        'result': deepcopy(result),
        'environment': deepcopy(environment),
        'evaluation': {
            'rating': max(0, min(5, int(evaluation.get('rating', 0) or 0))),
            'usable_frames': max(0, int(evaluation.get('usable_frames', 0) or 0)),
            'verdict': str(evaluation.get('verdict') or 'unrated') if str(evaluation.get('verdict') or 'unrated') in CALIBRATION_VERDICTS else 'unrated',
            'notes': str(evaluation.get('notes') or ''),
        },
        'tags': [str(tag).strip() for tag in run.get('tags', []) if str(tag).strip()] if isinstance(run.get('tags'), list) else [],
        'promoted_generation_profile': run.get('promoted_generation_profile') if isinstance(run.get('promoted_generation_profile'), str) else None,
        'promoted_production_preset': run.get('promoted_production_preset') if isinstance(run.get('promoted_production_preset'), str) else None,
    }


def _request_generation_profile(request: dict[str, Any]) -> dict[str, Any]:
    generation = request.get('generation') if isinstance(request.get('generation'), dict) else {}
    inputs = request.get('inputs') if isinstance(request.get('inputs'), dict) else {}
    prompt = request.get('prompt') if isinstance(request.get('prompt'), dict) else {}
    metadata = request.get('metadata') if isinstance(request.get('metadata'), dict) else {}
    requested_frames = metadata.get('requested_frames', generation.get('frames', 49))
    requested_fps = metadata.get('requested_fps', generation.get('fps', 24.0))
    resolution_class = metadata.get('requested_resolution_class')
    aspect_ratio = metadata.get('requested_aspect_ratio')
    if not resolution_class:
        width = generation.get('width')
        height = generation.get('height')
        resolution_class = f'{width}x{height}' if width and height else ''
    return {
        'provider_id': str(request.get('provider') or 'local_wangp'),
        'model_id': str(request.get('model') or 'wangp_template_model'),
        'reference_image': str(inputs.get('reference_image') or ''),
        'motion_video': str(inputs.get('motion_video') or ''),
        'positive_prompt': str(prompt.get('positive') or ''),
        'negative_prompt': str(prompt.get('negative') or ''),
        'requested_background_rgb': list(metadata.get('requested_background_rgb') or [0, 255, 0]),
        'seed': int(generation.get('seed', 0) or 0),
        'resolution_class': str(resolution_class or ''),
        'aspect_ratio': str(aspect_ratio or ''),
        'frames': int(requested_frames or generation.get('frames', 49) or 49),
        'fps': float(requested_fps or generation.get('fps', 24.0) or 24.0),
        'steps': int(generation.get('steps', 20) or 20),
        'prompt_profile_name': str(metadata.get('prompt_profile_name') or ''),
        'prompt_builder_state': deepcopy(metadata.get('prompt_builder_state')) if isinstance(metadata.get('prompt_builder_state'), dict) else {},
    }


def probe_environment() -> dict[str, Any]:
    result: dict[str, Any] = {
        'captured_at': _now(),
        'os': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python': platform.python_version(),
    }
    nvidia_smi = shutil.which('nvidia-smi')
    if nvidia_smi:
        try:
            completed = subprocess.run(
                [nvidia_smi, '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            if lines:
                gpus = []
                for line in lines:
                    parts = [part.strip() for part in line.split(',')]
                    gpus.append({
                        'name': parts[0] if len(parts) > 0 else '',
                        'memory_total_mb': int(float(parts[1])) if len(parts) > 1 and parts[1] else None,
                        'driver_version': parts[2] if len(parts) > 2 else '',
                    })
                result['nvidia_gpus'] = gpus
        except Exception:
            pass
    return result


def build_run_from_job(job_payload: dict[str, Any], *, environment: dict[str, Any] | None = None) -> dict[str, Any]:
    request = job_payload.get('request') if isinstance(job_payload.get('request'), dict) else {}
    profile = _request_generation_profile(request)
    result_payload = job_payload.get('result') if isinstance(job_payload.get('result'), dict) else {}
    metadata = result_payload.get('metadata') if isinstance(result_payload.get('metadata'), dict) else {}
    source_job_id = str(job_payload.get('job_id') or result_payload.get('job_id') or '')
    result = {
        'state': str(job_payload.get('state') or result_payload.get('state') or ''),
        'provider': str(job_payload.get('provider') or result_payload.get('provider') or profile.get('provider_id') or ''),
        'model': str(job_payload.get('model') or result_payload.get('model') or profile.get('model_id') or ''),
        'video_path': result_payload.get('video_path'),
        'job_directory': job_payload.get('job_directory'),
        'duration_seconds': job_payload.get('duration_seconds'),
        'started_at_utc': job_payload.get('started_at_utc'),
        'completed_at_utc': job_payload.get('completed_at_utc'),
        'actual_width': metadata.get('actual_width', metadata.get('width')),
        'actual_height': metadata.get('actual_height', metadata.get('height')),
        'actual_frames': metadata.get('actual_frames', metadata.get('frames')),
        'actual_fps': metadata.get('actual_fps', metadata.get('fps')),
        'resolution_match': metadata.get('resolution_match'),
        'frames_match': metadata.get('frames_match'),
        'fps_match': metadata.get('fps_match'),
        'error_code': result_payload.get('error_code'),
        'error_message': result_payload.get('error_message'),
    }
    safe_job = re.sub(r'[^a-zA-Z0-9_-]+', '-', source_job_id).strip('-_') or uuid.uuid4().hex[:12]
    return normalize_calibration_run({
        'id': f'cal_{safe_job}',
        'source_kind': 'generation_job',
        'source_job_id': source_job_id or None,
        'created_at': job_payload.get('completed_at_utc') or job_payload.get('started_at_utc') or _now(),
        'generation_profile': profile,
        'result': result,
        'environment': environment or probe_environment(),
        'evaluation': {},
    })


def build_manual_run(profile: dict[str, Any], *, environment: dict[str, Any] | None = None) -> dict[str, Any]:
    return normalize_calibration_run({
        'id': f'cal_manual_{uuid.uuid4().hex[:12]}',
        'source_kind': 'manual_snapshot',
        'created_at': _now(),
        'generation_profile': deepcopy(profile),
        'result': {'state': 'configuration_only'},
        'environment': environment or probe_environment(),
        'evaluation': {},
    })


def sync_jobs_to_runs(
    calibration_state: dict[str, Any] | None,
    jobs: Iterable[dict[str, Any]],
    *,
    environment: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    state = normalize_calibration_state(calibration_state)
    existing_job_ids = {run.get('source_job_id') for run in state['runs'] if run.get('source_job_id')}
    added: list[str] = []
    shared_environment = environment or probe_environment()
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get('job_id') or '')
        if not job_id or job_id in existing_job_ids:
            continue
        run = build_run_from_job(job, environment=shared_environment)
        state['runs'].append(run)
        existing_job_ids.add(job_id)
        added.append(run['id'])
    state['updated_at'] = _now()
    return state, added


def compare_generation_profiles(left: dict[str, Any], right: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = sorted(set(left.keys()) | set(right.keys()))
    differences: dict[str, dict[str, Any]] = {}
    for key in keys:
        a = left.get(key)
        b = right.get(key)
        if a != b:
            differences[key] = {'left': deepcopy(a), 'right': deepcopy(b)}
    return differences


def parse_variant_value(field: str, raw_value: str) -> Any:
    field = str(field)
    raw = str(raw_value).strip()
    if field in {'steps', 'frames', 'seed'}:
        value = int(raw)
        if field in {'steps', 'frames'} and value <= 0:
            raise ValueError(f'{field} deve essere positivo.')
        if field == 'seed' and value < 0:
            raise ValueError('seed non può essere negativo.')
        return value
    if field == 'fps':
        value = float(raw)
        if value <= 0:
            raise ValueError('fps deve essere positivo.')
        return value
    if field in {'resolution_class', 'aspect_ratio', 'positive_prompt', 'negative_prompt'}:
        if not raw:
            raise ValueError(f'{field} non può essere vuoto.')
        return raw
    raise ValueError(f'Parametro non supportato: {field}')


def build_single_parameter_variant(profile: dict[str, Any], field: str, value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if field not in VARIANT_FIELDS:
        raise ValueError(f'Parametro non supportato: {field}')
    result = deepcopy(profile)
    old_value = result.get(field)
    result[field] = deepcopy(value)
    differences = compare_generation_profiles(profile, result)
    if not differences:
        raise ValueError('La variante non modifica alcun parametro.')
    if set(differences) != {field}:
        raise ValueError('La variante deve modificare esattamente un parametro.')
    if field != 'seed' and result.get('seed') != profile.get('seed'):
        raise ValueError('Il seed deve restare invariato nelle varianti non-seed.')
    return result, {'field': field, 'before': old_value, 'after': value, 'seed_preserved': field == 'seed' or result.get('seed') == profile.get('seed')}


def run_summary(run: dict[str, Any]) -> str:
    normalized = normalize_calibration_run(run)
    profile = normalized['generation_profile']
    result = normalized['result']
    evaluation = normalized['evaluation']
    duration = result.get('duration_seconds')
    duration_text = f'{float(duration):.1f}s' if isinstance(duration, (int, float)) else '—'
    actual = '—'
    if result.get('actual_width') and result.get('actual_height'):
        actual = f"{result.get('actual_width')}×{result.get('actual_height')} / {result.get('actual_frames') or '—'}f / {result.get('actual_fps') or '—'}fps"
    return '\n'.join([
        f"Run: {normalized['id']}",
        f"Job: {normalized.get('source_job_id') or 'snapshot manuale'}",
        f"Config: seed {profile.get('seed', '—')} · {profile.get('resolution_class', '—')} {profile.get('aspect_ratio', '')} · {profile.get('frames', '—')}f · {profile.get('fps', '—')}fps · {profile.get('steps', '—')} steps",
        f"Output reale: {actual}",
        f"Tempo job: {duration_text}",
        f"Valutazione: {evaluation.get('rating', 0)}/5 · {evaluation.get('verdict', 'unrated')} · frame utili {evaluation.get('usable_frames', 0)}",
    ])
