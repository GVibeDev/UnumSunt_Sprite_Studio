from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from queue import Empty, Queue
import re
import shutil
import subprocess
from threading import Thread
import time
from typing import Any

from app.generation.base import GenerationJobContext, VideoGeneratorProvider
from app.generation.errors import (
    GenerationCancelledError,
    InvalidGenerationRequestError,
    LocalRuntimeNotInstalledError,
    OutputNotFoundError,
    ProcessCrashError,
    PythonEnvironmentBrokenError,
)
from app.generation.models import (
    GenerationProgress,
    GenerationRequest,
    GenerationResult,
    ProviderCapabilities,
)
from app.video_source import VideoOpenError, VideoSource
from app.runtime_paths import local_data_root
from app.runtime_gpu_compat import probe_torch_runtime_gpu


VIDEO_EXTENSIONS = {'.mp4', '.m4v', '.mov', '.webm', '.avi'}


@dataclass
class LocalWanGPConfig:
    python_executable: str = ''
    wangp_script: str = ''
    settings_template: str = ''
    working_directory: str = ''
    verbose: int = 2
    strict_python_311: bool = True
    require_template: bool = True
    process_timeout_seconds: int = 0
    extra_arguments: list[str] = field(default_factory=list)

    @staticmethod
    def default_path() -> Path:
        return local_data_root() / 'local_wangp.json'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'LocalWanGPConfig':
        return cls(
            python_executable=str(data.get('python_executable', '')),
            wangp_script=str(data.get('wangp_script', '')),
            settings_template=str(data.get('settings_template', '')),
            working_directory=str(data.get('working_directory', '')),
            verbose=int(data.get('verbose', 2)),
            strict_python_311=bool(data.get('strict_python_311', True)),
            require_template=bool(data.get('require_template', True)),
            process_timeout_seconds=max(0, int(data.get('process_timeout_seconds', 0))),
            extra_arguments=[str(value) for value in data.get('extra_arguments', [])],
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> 'LocalWanGPConfig':
        target = Path(path) if path is not None else cls.default_path()
        if not target.exists():
            return cls()
        try:
            payload = json.loads(target.read_text(encoding='utf-8'))
        except Exception:
            return cls()
        if not isinstance(payload, dict):
            return cls()
        return cls.from_dict(payload)

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.default_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')
        return target


@dataclass
class HealthCheckItem:
    name: str
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LocalWanGPHealthReport:
    available: bool
    python_version: str | None
    checks: list[HealthCheckItem]
    warnings: list[str]
    checked_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'available': self.available,
            'python_version': self.python_version,
            'checks': [item.to_dict() for item in self.checks],
            'warnings': list(self.warnings),
            'checked_at_utc': self.checked_at_utc,
        }

    def summary(self) -> str:
        lines = [
            'Local WanGP bridge: ' + ('READY' if self.available else 'NOT READY'),
        ]
        if self.python_version:
            lines.append(f'Python: {self.python_version}')
        for item in self.checks:
            lines.append(f"{'✓' if item.ok else '✗'} {item.name}: {item.detail}")
        for warning in self.warnings:
            lines.append(f'⚠ {warning}')
        return '\n'.join(lines)


class WanGPProgressParser:
    STEP_RE = re.compile(r'\[(?P<current>\d+)\s*/\s*(?P<total>\d+)\]')
    ALT_STEP_RE = re.compile(r'(?P<current>\d+)\s*(?:/|of)\s*(?P<total>\d+)', re.IGNORECASE)

    PHASES = (
        ('loading model', 'loading_model', 0.08, 0.18),
        ('load model', 'loading_model', 0.08, 0.18),
        ('preprocess', 'preprocessing', 0.18, 0.27),
        ('denois', 'denoising', 0.27, 0.82),
        ('vae', 'decoding', 0.82, 0.93),
        ('decod', 'decoding', 0.82, 0.93),
        ('saving', 'saving', 0.93, 0.99),
        ('save', 'saving', 0.93, 0.99),
    )

    def parse(self, line: str) -> GenerationProgress | None:
        normalized = line.strip()
        if not normalized:
            return None
        lower = normalized.lower()
        state = 'starting'
        start_fraction = 0.03
        end_fraction = 0.08
        for token, phase_state, phase_start, phase_end in self.PHASES:
            if token in lower:
                state = phase_state
                start_fraction = phase_start
                end_fraction = phase_end
                break
        match = self.STEP_RE.search(normalized) or self.ALT_STEP_RE.search(normalized)
        current = None
        total = None
        fraction = start_fraction
        if match:
            current = int(match.group('current'))
            total = max(1, int(match.group('total')))
            ratio = max(0.0, min(1.0, current / total))
            fraction = start_fraction + (end_fraction - start_fraction) * ratio
        return GenerationProgress(
            state=state,
            fraction=fraction,
            message=normalized,
            current_step=current,
            total_steps=total,
        )


class WanGPJobAdapter:
    PLACEHOLDERS = {
        '${JOB_ID}': lambda request, paths: request.job_id,
        '${REFERENCE_IMAGE}': lambda request, paths: paths.get('reference_image'),
        '${MOTION_VIDEO}': lambda request, paths: paths.get('motion_video'),
        '${POSITIVE_PROMPT}': lambda request, paths: request.positive_prompt,
        '${NEGATIVE_PROMPT}': lambda request, paths: request.negative_prompt,
        '${SEED}': lambda request, paths: request.seed,
        '${WIDTH}': lambda request, paths: request.width,
        '${HEIGHT}': lambda request, paths: request.height,
        '${FRAMES}': lambda request, paths: request.frames,
        '${FPS}': lambda request, paths: request.fps,
        '${STEPS}': lambda request, paths: request.steps,
        '${MODEL}': lambda request, paths: request.model,
        '${OUTPUT_DIR}': lambda request, paths: paths.get('output_directory'),
        '${BACKGROUND_RGB}': lambda request, paths: ','.join(str(int(v)) for v in request.metadata.get('requested_background_rgb', [0, 255, 0])),
        '${BACKGROUND_RGB_LIST}': lambda request, paths: [int(v) for v in request.metadata.get('requested_background_rgb', [0, 255, 0])],
        '${BACKGROUND_R}': lambda request, paths: int(request.metadata.get('requested_background_rgb', [0, 255, 0])[0]),
        '${BACKGROUND_G}': lambda request, paths: int(request.metadata.get('requested_background_rgb', [0, 255, 0])[1]),
        '${BACKGROUND_B}': lambda request, paths: int(request.metadata.get('requested_background_rgb', [0, 255, 0])[2]),
        '${BACKGROUND_HEX}': lambda request, paths: '#%02X%02X%02X' % tuple(int(v) for v in request.metadata.get('requested_background_rgb', [0, 255, 0])),
    }

    def build_payload(
        self,
        request: GenerationRequest,
        config: LocalWanGPConfig,
        paths: dict[str, Any],
    ) -> dict[str, Any]:
        template_path = Path(config.settings_template).expanduser() if config.settings_template else None
        if template_path and template_path.is_file():
            try:
                template = json.loads(template_path.read_text(encoding='utf-8'))
            except Exception as exc:
                raise InvalidGenerationRequestError(
                    f'The WanGP template is not valid JSON: {exc}'
                ) from exc
            if not isinstance(template, dict):
                raise InvalidGenerationRequestError('The WanGP template must contain a JSON object.')
            payload = self._replace(template, request, paths)
            if self.is_official_settings_payload(payload):
                payload = self._bind_official_settings(payload, request, paths)
                self.validate_official_bindings(payload, request, paths)
            return payload

        return {
            'schema': 'unum-sunt-wangp-adapter-v1',
            '__unum_sunt_request__': request.to_dict(),
            'task': request.task,
            'model': request.model,
            'inputs': {
                'reference_image': paths.get('reference_image'),
                'motion_video': paths.get('motion_video'),
            },
            'prompt': {
                'positive': request.positive_prompt,
                'negative': request.negative_prompt,
            },
            'generation': {
                'seed': request.seed,
                'width': request.width,
                'height': request.height,
                'frames': request.frames,
                'fps': request.fps,
                'steps': request.steps,
            },
            'output': {
                'directory': paths.get('output_directory'),
                'requested_background_rgb': request.metadata.get('requested_background_rgb'),
                'background_mode': request.metadata.get('background_mode'),
            },
        }

    @staticmethod
    def is_official_settings_payload(payload: dict[str, Any]) -> bool:
        return (
            'settings_version' in payload
            or 'model_type' in payload
            or 'model_filename' in payload
        )

    @staticmethod
    def _required_reference_keys(payload: dict[str, Any]) -> list[str]:
        """Resolve the official WanGP attachment fields required by a preset.

        WanGP uses different image slots for different workflows:
        ``image_refs`` is the character/reference gallery used by Animate and
        other modes whose ``video_prompt_type`` contains ``I``; ``image_start``
        is the start-frame input enabled by ``image_prompt_type`` containing
        ``S``.  Exported settings omit the actual media paths, so the bridge
        must restore them according to the preset semantics rather than always
        assuming image-to-video start-frame mode.
        """
        video_prompt_type = str(payload.get('video_prompt_type', '') or '')
        image_prompt_type = str(payload.get('image_prompt_type', '') or '')
        model_type = str(payload.get('model_type', '') or '').strip().lower()

        keys: list[str] = []
        if 'I' in video_prompt_type or model_type == 'animate':
            keys.append('image_refs')
        if 'S' in image_prompt_type:
            keys.append('image_start')
        if not keys:
            # Backward-compatible fallback for ordinary I2V presets that do
            # not serialize their prompt-type selectors.
            keys.append('image_start')
        return keys

    @classmethod
    def _bind_official_settings(
        cls,
        payload: dict[str, Any],
        request: GenerationRequest,
        paths: dict[str, Any],
    ) -> dict[str, Any]:
        # WanGP exported settings intentionally omit media attachments. The
        # official CLI loader accepts absolute paths in ATTACHMENT_KEYS, but
        # the correct image key depends on the selected workflow.
        payload['prompt'] = request.positive_prompt
        payload['negative_prompt'] = request.negative_prompt
        payload['resolution'] = f'{int(request.width)}x{int(request.height)}'
        payload['video_length'] = int(request.frames)
        payload['seed'] = int(request.seed)
        payload['num_inference_steps'] = int(request.steps)

        reference_image = paths.get('reference_image')
        if reference_image:
            required_keys = cls._required_reference_keys(payload)
            for key in ('image_refs', 'image_start'):
                if key in required_keys:
                    payload[key] = [str(reference_image)]
                else:
                    # Remove stale adapter fields from a previous conversion;
                    # preserve only slots actually requested by the preset.
                    payload.pop(key, None)

        motion_video = paths.get('motion_video')
        if motion_video:
            payload['video_guide'] = str(motion_video)
        else:
            payload.pop('video_guide', None)

        return payload

    @staticmethod
    def validate_official_bindings(
        payload: dict[str, Any],
        request: GenerationRequest,
        paths: dict[str, Any],
    ) -> None:
        expected = {
            'prompt': request.positive_prompt,
            'negative_prompt': request.negative_prompt,
            'resolution': f'{int(request.width)}x{int(request.height)}',
            'video_length': int(request.frames),
            'seed': int(request.seed),
            'num_inference_steps': int(request.steps),
        }
        mismatches = [
            f'{key}: expected {expected_value!r}, found {payload.get(key)!r}'
            for key, expected_value in expected.items()
            if payload.get(key) != expected_value
        ]

        reference_image = paths.get('reference_image')
        for attachment_key in WanGPJobAdapter._required_reference_keys(payload):
            attachment = payload.get(attachment_key)
            image_values = attachment if isinstance(attachment, list) else [attachment]
            if reference_image and str(reference_image) not in [str(value) for value in image_values if value]:
                mismatches.append(
                    f'{attachment_key}: reference image not attached to the WanGP job'
                )

        motion_video = paths.get('motion_video')
        if motion_video and str(payload.get('video_guide', '')) != str(motion_video):
            mismatches.append('video_guide: motion reference not attached to the WanGP job')

        if mismatches:
            raise InvalidGenerationRequestError(
                'Incomplete WanGP template binding: ' + '; '.join(mismatches)
            )

    def binding_report(
        self,
        payload: dict[str, Any],
        request: GenerationRequest,
        paths: dict[str, Any],
    ) -> dict[str, Any]:
        official = self.is_official_settings_payload(payload)
        report: dict[str, Any] = {
            'adapter_mode': 'official_settings_direct' if official else 'placeholder_or_generic',
            'official_settings_detected': official,
            'bound_fields': [],
            'notes': [],
        }
        if official:
            report['template_model_type'] = payload.get('model_type')
            report['template_model_filename'] = payload.get('model_filename')
            report['bound_fields'] = [
                'prompt',
                'negative_prompt',
                'resolution',
                'video_length',
                'seed',
                'num_inference_steps',
            ]
            if paths.get('reference_image'):
                report['bound_fields'].extend(self._required_reference_keys(payload))
            if paths.get('motion_video'):
                report['bound_fields'].append('video_guide')
            report['notes'].append(
                'FPS not overridden: WanGP keeps force_fps from the preset (for Animate, the control value uses the guide video frame rate).'
            )
            report['notes'].append(
                'The model/checkpoint remains the one defined by the WanGP preset.'
            )
        return report

    def _replace(self, value: Any, request: GenerationRequest, paths: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: self._replace(item, request, paths) for key, item in value.items()}
        if isinstance(value, list):
            return [self._replace(item, request, paths) for item in value]
        if not isinstance(value, str):
            return value

        for placeholder, resolver in self.PLACEHOLDERS.items():
            if value == placeholder:
                return resolver(request, paths)

        result = value
        for placeholder, resolver in self.PLACEHOLDERS.items():
            replacement = resolver(request, paths)
            result = result.replace(placeholder, '' if replacement is None else str(replacement))
        return result


class LocalWanGPProvider(VideoGeneratorProvider):
    provider_id = 'local_wangp'
    display_name = 'Local WAN / WanGP Bridge'

    def __init__(self, config: LocalWanGPConfig | None = None) -> None:
        self.config = config or LocalWanGPConfig.load()
        self.progress_parser = WanGPProgressParser()
        self.adapter = WanGPJobAdapter()

    def update_config(self, config: LocalWanGPConfig) -> None:
        self.config = config

    def uses_standard_wangp_layout(self) -> bool:
        if not self.config.wangp_script:
            return False
        return Path(self.config.wangp_script).expanduser().name.lower() == 'wgp.py'

    def resolve_working_directory(self) -> tuple[Path, str | None]:
        """Return the runtime cwd and an optional corrective warning.

        WanGP resolves resources such as ``models/_settings.json`` relative to
        the current working directory. For the standard ``wgp.py`` launcher,
        the repository root containing the script is therefore authoritative.
        Development fixtures may still use a separately configured cwd.
        """
        script_path = Path(self.config.wangp_script).expanduser()
        script_directory = script_path.parent
        configured = (
            Path(self.config.working_directory).expanduser()
            if self.config.working_directory
            else None
        )

        if not self.uses_standard_wangp_layout():
            if configured and configured.is_dir():
                return configured, None
            if configured:
                return script_directory, (
                    f'Configured working directory is unavailable ({configured}); using the script folder: {script_directory}'
                )
            return script_directory, None

        marker = Path('models') / '_settings.json'
        if configured and configured.is_dir() and (configured / marker).is_file():
            return configured, None

        if (script_directory / marker).is_file():
            if configured and configured != script_directory:
                return script_directory, (
                    f'Working directory automatically corrected from {configured} to {script_directory}: WanGP requires {marker.as_posix()} relative to its own root.'
                )
            return script_directory, None

        if configured and configured.is_dir():
            return configured, None
        return script_directory, None

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            image_to_video=True,
            motion_reference=True,
            negative_prompt=True,
            fixed_seed=True,
            cancellation=True,
            progress_reporting=True,
            cost_estimation=False,
        )

    def health_check(self) -> LocalWanGPHealthReport:
        checks: list[HealthCheckItem] = []
        warnings: list[str] = []
        python_version: str | None = None

        python_path = Path(self.config.python_executable).expanduser() if self.config.python_executable else None
        python_ok = bool(python_path and python_path.is_file())
        checks.append(HealthCheckItem('Python executable', python_ok, str(python_path) if python_path else 'not configured'))

        script_path = Path(self.config.wangp_script).expanduser() if self.config.wangp_script else None
        script_ok = bool(script_path and script_path.is_file())
        checks.append(HealthCheckItem('WanGP wgp.py', script_ok, str(script_path) if script_path else 'not configured'))

        template_ok = True
        if self.config.require_template:
            template_path = Path(self.config.settings_template).expanduser() if self.config.settings_template else None
            template_ok = bool(template_path and template_path.is_file())
            template_detail = str(template_path) if template_path else 'not configured'
            if template_ok and template_path is not None:
                try:
                    template_payload = json.loads(template_path.read_text(encoding='utf-8'))
                    if not isinstance(template_payload, dict):
                        raise ValueError('JSON root is not an object')
                    if self.uses_standard_wangp_layout() and not self.adapter.is_official_settings_payload(template_payload):
                        template_ok = False
                        template_detail += ' · this is not an official WanGP settings export (model_type/model_filename/settings_version is missing)'
                except Exception as exc:
                    template_ok = False
                    template_detail += f' · invalid JSON: {exc}'
            checks.append(HealthCheckItem('WanGP settings template', template_ok, template_detail))
        elif self.config.settings_template:
            template_path = Path(self.config.settings_template).expanduser()
            template_ok = template_path.is_file()
            checks.append(HealthCheckItem('WanGP settings template', template_ok, str(template_path)))
        else:
            warnings.append('No template configured: the generic payload adapter will be used, intended mainly for testing and integration.')

        working_directory, working_warning = self.resolve_working_directory()
        working_ok = working_directory.is_dir()
        checks.append(
            HealthCheckItem(
                'WanGP runtime directory',
                working_ok,
                str(working_directory) if working_ok else f'folder not found: {working_directory}',
            )
        )
        if working_warning:
            warnings.append(working_warning)

        runtime_layout_ok = True
        if self.uses_standard_wangp_layout():
            settings_marker = working_directory / 'models' / '_settings.json'
            runtime_layout_ok = settings_marker.is_file()
            checks.append(
                HealthCheckItem(
                    'WanGP models/_settings.json',
                    runtime_layout_ok,
                    str(settings_marker) if runtime_layout_ok else f'file not found: {settings_marker}',
                )
            )

        version_ok = False
        if python_ok:
            try:
                completed = subprocess.run(
                    [str(python_path), '-c', 'import platform,sys; print(platform.python_version()); print(sys.executable)'],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
                python_version = lines[0] if lines else None
                version_ok = completed.returncode == 0 and bool(python_version)
                detail = python_version or completed.stderr.strip() or f'exit {completed.returncode}'
                checks.append(HealthCheckItem('Python launch', version_ok, detail))
                if version_ok and self.config.strict_python_311 and not python_version.startswith('3.11.'):
                    version_ok = False
                    checks[-1] = HealthCheckItem('Python launch', False, f'{python_version}; Python 3.11.x required')
                elif version_ok and not python_version.startswith('3.11.'):
                    warnings.append(f'Python {python_version} accepted only because strict Python 3.11 checking is disabled.')
            except Exception as exc:
                checks.append(HealthCheckItem('Python launch', False, str(exc)))

        # R5c4: the PyTorch/GPU contract belongs to real AI runtimes only.
        # Development fixtures intentionally run on the Core/build interpreter
        # without PyTorch; making torch mandatory there breaks the regression
        # suite and couples the standalone build environment to the AI runtime.
        torch_required = bool(self.config.strict_python_311)
        torch_ok = not torch_required
        gpu_compat_required = self.uses_standard_wangp_layout() and torch_required
        gpu_compat_ok = not gpu_compat_required
        if python_ok and version_ok and torch_required:
            torch_probe = probe_torch_runtime_gpu(python_path, runner=subprocess.run, timeout=30)
            torch_ok = torch_probe.available
            checks.append(HealthCheckItem('PyTorch runtime', torch_ok, torch_probe.detail()))
            if gpu_compat_required:
                gpu_compat_ok = torch_probe.available and torch_probe.cuda_available and torch_probe.default_device_compatible
                checks.append(HealthCheckItem('GPU ↔ PyTorch compatibility', gpu_compat_ok, torch_probe.detail()))
            if torch_probe.available and not torch_probe.cuda_available:
                warnings.append('PyTorch can be imported, but torch.cuda.is_available() is False. Check the driver and CUDA runtime.')
            elif gpu_compat_required and torch_probe.available and torch_probe.cuda_available and not torch_probe.default_device_compatible:
                warnings.append(
                    'The default GPU is not included in the CUDA architectures compiled into the installed PyTorch wheel. Local generation is blocked before WanGP starts.'
                )
        elif python_ok and version_ok and not torch_required:
            warnings.append('PyTorch/GPU check skipped for development/mock runtime: the real AI runtime remains separate from the Core/build environment.')

        available = (
            python_ok
            and script_ok
            and template_ok
            and working_ok
            and runtime_layout_ok
            and version_ok
            and torch_ok
            and gpu_compat_ok
        )
        return LocalWanGPHealthReport(
            available=available,
            python_version=python_version,
            checks=checks,
            warnings=warnings,
            checked_at_utc=datetime.now(timezone.utc).isoformat(),
        )

    def validate_request(self, request: GenerationRequest) -> None:
        if request.task != 'image_to_video':
            raise InvalidGenerationRequestError('The local bridge supports image_to_video.')
        if not request.reference_image:
            raise InvalidGenerationRequestError('The local provider requires a reference image.')
        reference = Path(request.reference_image).expanduser()
        if not reference.is_file():
            raise InvalidGenerationRequestError(f'Reference image not found: {reference}')
        motion = Path(request.motion_video).expanduser() if request.motion_video else None
        if motion is not None and not motion.is_file():
            raise InvalidGenerationRequestError(f'Motion reference not found: {motion}')
        if request.width <= 0 or request.height <= 0 or request.frames <= 0 or request.fps <= 0:
            raise InvalidGenerationRequestError('Dimensions, frame count, and FPS must be positive.')
        contract = request.metadata.get('wan_contract')
        if isinstance(contract, dict):
            if request.width % 16 != 0 or request.height % 16 != 0:
                raise InvalidGenerationRequestError(
                    'The contracted WanGP dimensions must be multiples of 16.'
                )
            if request.frames < 1 or (request.frames - 1) % 4 != 0:
                raise InvalidGenerationRequestError(
                    'The contracted WanGP frame count must follow the 4n+1 form.'
                )
        report = self.health_check()
        if not report.available:
            raise LocalRuntimeNotInstalledError(report.summary())

        # Validate the actual template contract before a long external job is
        # submitted. This catches invalid JSON and missing media bindings in
        # the UI's "Valida" action, not only after the worker thread starts.
        self.adapter.build_payload(
            request,
            self.config,
            {
                'reference_image': str(reference.resolve()),
                'motion_video': str(motion.resolve()) if motion is not None else None,
                'output_directory': '',
            },
        )

    def run(self, request: GenerationRequest, context: GenerationJobContext) -> GenerationResult:
        self.validate_request(request)
        self._check_cancel(context)
        context.progress_callback(GenerationProgress('validating', 0.02, 'WanGP runtime validation'))

        copied_paths = self._copy_inputs(request, context)
        copied_paths['output_directory'] = str(context.output_directory.resolve())
        payload = self.adapter.build_payload(request, self.config, copied_paths)
        settings_path = context.job_directory / 'wangp_settings.json'
        settings_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        resolved_working_directory, working_warning = self.resolve_working_directory()
        (context.job_directory / 'provider_settings.json').write_text(
            json.dumps(
                {
                    'provider': self.provider_id,
                    'config': self.config.to_dict(),
                    'resolved_working_directory': str(resolved_working_directory),
                    'working_directory_warning': working_warning,
                    'template_binding': self.adapter.binding_report(payload, request, copied_paths),
                    'generation_contract': request.metadata.get('wan_contract'),
                    'command_preview': self._build_command(settings_path, context.output_directory, dry_run=bool(request.metadata.get('dry_run'))),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding='utf-8',
        )

        dry_run = bool(request.metadata.get('dry_run'))
        context.progress_callback(GenerationProgress('starting', 0.04, 'Starting external WanGP process'))
        return_code = self._run_process(
            settings_path=settings_path,
            context=context,
            dry_run=dry_run,
        )
        if return_code != 0:
            raise ProcessCrashError(f'WanGP exited with code {return_code}. See logs/stderr.log.')

        if dry_run:
            manifest = {
                'schema': 'unum-sunt-generation-manifest-v3',
                'job_id': request.job_id,
                'provider': self.provider_id,
                'model': request.model,
                'state': 'completed',
                'dry_run': True,
                'settings_file': str(settings_path),
                'background_contract': {
                    'requested_rgb': request.metadata.get('requested_background_rgb'),
                    'mode': request.metadata.get('background_mode'),
                },
                'generation_contract': request.metadata.get('wan_contract'),
            }
            (context.job_directory / 'generation_manifest.json').write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
            return GenerationResult(
                job_id=request.job_id,
                state='completed',
                provider=self.provider_id,
                model=request.model,
                video_path=None,
                seed=request.seed,
                metadata={
                    'dry_run': True,
                    'settings_file': str(settings_path),
                    'wan_contract': request.metadata.get('wan_contract'),
                    'requested_frames': request.metadata.get('requested_frames', request.frames),
                    'effective_frames': request.frames,
                    'requested_fps': request.metadata.get('requested_fps', request.fps),
                    'effective_fps': request.metadata.get('effective_fps'),
                    'fps_source': request.metadata.get('fps_source', 'request'),
                },
            )

        context.progress_callback(GenerationProgress('saving', 0.97, 'Searching for WanGP video output'))
        output_path = self._find_output_video(context.output_directory)
        metadata = self._validate_video(output_path)
        actual_width = metadata.get('width')
        actual_height = metadata.get('height')
        actual_frames = metadata.get('frames')
        actual_fps = metadata.get('fps')
        planned_fps = request.metadata.get('effective_fps')
        resolution_match = actual_width == request.width and actual_height == request.height
        frames_match = actual_frames == request.frames
        fps_match = None
        if planned_fps is not None and actual_fps is not None:
            fps_match = abs(float(actual_fps) - float(planned_fps)) <= 0.01
        metadata.update({
            'actual_width': actual_width,
            'actual_height': actual_height,
            'actual_frames': actual_frames,
            'actual_fps': actual_fps,
            'planned_width': request.width,
            'planned_height': request.height,
            'requested_resolution_class': request.metadata.get('requested_resolution_class'),
            'requested_aspect_ratio': request.metadata.get('requested_aspect_ratio'),
            'requested_frames': request.metadata.get('requested_frames', request.frames),
            'effective_frames': request.frames,
            'requested_fps': request.metadata.get('requested_fps', request.fps),
            'effective_fps': planned_fps,
            'fps_source': request.metadata.get('fps_source', 'request'),
            'resolution_match': resolution_match,
            'frames_match': frames_match,
            'fps_match': fps_match,
            'wan_contract': request.metadata.get('wan_contract'),
            'execution_contract': {
                'planned': {
                    'width': request.width,
                    'height': request.height,
                    'frames': request.frames,
                    'fps': planned_fps,
                },
                'actual': {
                    'width': actual_width,
                    'height': actual_height,
                    'frames': actual_frames,
                    'fps': actual_fps,
                },
                'matches': {
                    'resolution': resolution_match,
                    'frames': frames_match,
                    'fps': fps_match,
                },
            },
        })
        metadata['requested_background_rgb'] = request.metadata.get('requested_background_rgb')
        metadata['background_mode'] = request.metadata.get('background_mode')
        manifest = {
            'schema': 'unum-sunt-generation-manifest-v3',
            'job_id': request.job_id,
            'provider': self.provider_id,
            'model': request.model,
            'video_path': str(output_path),
            'seed': request.seed,
            'metadata': metadata,
            'settings_file': str(settings_path),
            'stdout_log': str(context.logs_directory / 'stdout.log'),
            'stderr_log': str(context.logs_directory / 'stderr.log'),
        }
        (context.job_directory / 'generation_manifest.json').write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        context.progress_callback(GenerationProgress('saving', 0.995, 'WanGP output validated'))
        return GenerationResult(
            job_id=request.job_id,
            state='completed',
            provider=self.provider_id,
            model=request.model,
            video_path=str(output_path),
            seed=request.seed,
            metadata=metadata,
        )

    def _copy_inputs(self, request: GenerationRequest, context: GenerationJobContext) -> dict[str, str | None]:
        result: dict[str, str | None] = {'reference_image': None, 'motion_video': None}
        for field_name, source_value in (
            ('reference_image', request.reference_image),
            ('motion_video', request.motion_video),
        ):
            if not source_value:
                continue
            source = Path(source_value).expanduser().resolve()
            target = context.input_directory / source.name
            if source != target:
                shutil.copy2(source, target)
            result[field_name] = str(target.resolve())
        return result

    def _build_command(self, settings_path: Path, output_directory: Path, *, dry_run: bool) -> list[str]:
        command = [
            str(Path(self.config.python_executable).expanduser()),
            str(Path(self.config.wangp_script).expanduser()),
            '--process',
            str(settings_path.resolve()),
            '--output-dir',
            str(output_directory.resolve()),
            '--verbose',
            str(max(0, int(self.config.verbose))),
        ]
        if dry_run:
            command.append('--dry-run')
        command.extend(self.config.extra_arguments)
        return command

    def _run_process(self, *, settings_path: Path, context: GenerationJobContext, dry_run: bool) -> int:
        command = self._build_command(settings_path, context.output_directory, dry_run=dry_run)
        working_dir, _working_warning = self.resolve_working_directory()
        creationflags = 0
        if os.name == 'nt' and hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            process = subprocess.Popen(
                command,
                cwd=str(working_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=creationflags,
            )
        except FileNotFoundError as exc:
            raise PythonEnvironmentBrokenError(f'Unable to start the runtime: {exc}') from exc
        except OSError as exc:
            raise ProcessCrashError(f'Failed to start WanGP process: {exc}') from exc

        queue: Queue[tuple[str, str | None]] = Queue()

        def reader(name: str, stream) -> None:
            try:
                for line in iter(stream.readline, ''):
                    queue.put((name, line))
            finally:
                queue.put((name, None))
                stream.close()

        threads = [
            Thread(target=reader, args=('stdout', process.stdout), daemon=True),
            Thread(target=reader, args=('stderr', process.stderr), daemon=True),
        ]
        for thread in threads:
            thread.start()

        stdout_path = context.logs_directory / 'stdout.log'
        stderr_path = context.logs_directory / 'stderr.log'
        active_streams = {'stdout', 'stderr'}
        start_time = time.monotonic()
        last_stdout: deque[str] = deque(maxlen=20)
        last_stderr: deque[str] = deque(maxlen=20)

        with stdout_path.open('w', encoding='utf-8') as stdout_file, stderr_path.open('w', encoding='utf-8') as stderr_file:
            while process.poll() is None or active_streams:
                if context.cancel_event.is_set():
                    self._terminate_process(process)
                    raise GenerationCancelledError('WanGP generation cancelled by the user.')
                if self.config.process_timeout_seconds > 0 and time.monotonic() - start_time > self.config.process_timeout_seconds:
                    self._terminate_process(process)
                    raise ProcessCrashError('WanGP process timed out.')
                try:
                    source, line = queue.get(timeout=0.10)
                except Empty:
                    continue
                if line is None:
                    active_streams.discard(source)
                    continue
                if source == 'stdout':
                    stdout_file.write(line)
                    stdout_file.flush()
                    last_stdout.append(line.strip())
                    progress = self.progress_parser.parse(line)
                    if progress is not None:
                        context.progress_callback(progress)
                else:
                    stderr_file.write(line)
                    stderr_file.flush()
                    last_stderr.append(line.strip())
                    progress = self.progress_parser.parse(line)
                    if progress is not None:
                        context.progress_callback(progress)

        return_code = process.wait()
        if return_code != 0:
            diagnostic_lines = [line for line in last_stderr if line]
            if not diagnostic_lines:
                diagnostic_lines = [
                    line for line in last_stdout
                    if line and (
                        '[error]' in line.lower()
                        or 'error' in line.lower()
                        or 'must provide' in line.lower()
                        or 'traceback' in line.lower()
                    )
                ]
            if not diagnostic_lines:
                diagnostic_lines = [line for line in last_stdout if line]
            detail = ' | '.join(diagnostic_lines[-10:])
            suffix = f': {detail}' if detail else ''
            raise ProcessCrashError(
                f'WanGP exited with code {return_code}{suffix}'
            )
        return return_code

    @staticmethod
    def _terminate_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    @staticmethod
    def _find_output_video(output_directory: Path) -> Path:
        candidates = [
            path
            for path in output_directory.rglob('*')
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS and path.stat().st_size > 0
        ]
        if not candidates:
            raise OutputNotFoundError('WanGP did not produce any video file in the output folder.')
        return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.stat().st_size))

    @staticmethod
    def _validate_video(path: Path) -> dict[str, Any]:
        source = VideoSource()
        try:
            metadata = source.open(path)
        except VideoOpenError as exc:
            raise OutputNotFoundError(f'The produced file is not a readable video: {exc}') from exc
        finally:
            source.close()
        return {
            'duration': metadata.duration_seconds,
            'width': metadata.width,
            'height': metadata.height,
            'fps': metadata.fps,
            'frames': metadata.frame_count,
            'file_size_bytes': path.stat().st_size,
        }

    @staticmethod
    def _check_cancel(context: GenerationJobContext) -> None:
        if context.cancel_event.is_set():
            raise GenerationCancelledError('Generation cancelled by the user.')
