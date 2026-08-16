from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.generation.base import GenerationJobContext, ImageGeneratorProvider
from app.generation.errors import (
    GenerationCancelledError,
    InvalidGenerationRequestError,
    LocalRuntimeNotInstalledError,
    OutputNotFoundError,
    ProcessCrashError,
)
from app.generation.local_wangp import LocalWanGPConfig, LocalWanGPProvider
from app.runtime_paths import local_data_root
from app.version import APP_VERSION
from app.generation.models import (
    GenerationProgress,
    GenerationRequest,
    GenerationResult,
    ProviderCapabilities,
)


IMAGE_EXTENSIONS = {'.png', '.webp', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}


@dataclass
class LocalWanGPImageConfig:
    """Image-generation configuration isolated from the video preset.

    Runtime paths can be inherited from the validated Local WanGP bridge, while
    the image settings template remains independent. R5c6b additionally exposes
    WanGP/mmgp memory controls without changing the external runtime itself.
    """

    MANAGED_ARGUMENTS = ('--profile', '--perc-reserved-mem-max')

    python_executable: str = ''
    wangp_script: str = ''
    settings_template: str = ''
    working_directory: str = ''
    verbose: int = 2
    strict_python_311: bool = True
    require_template: bool = True
    process_timeout_seconds: int = 0
    extra_arguments: list[str] = field(default_factory=list)
    memory_profile: str = ''
    reserved_memory_max: float = 0.0

    @staticmethod
    def default_path() -> Path:
        return local_data_root() / 'local_wangp_image.json'

    @classmethod
    def from_video_config(cls, config: LocalWanGPConfig) -> 'LocalWanGPImageConfig':
        return cls(
            python_executable=config.python_executable,
            wangp_script=config.wangp_script,
            working_directory=config.working_directory,
            verbose=config.verbose,
            strict_python_311=config.strict_python_311,
            require_template=True,
            process_timeout_seconds=config.process_timeout_seconds,
            extra_arguments=list(config.extra_arguments),
            memory_profile='',
            reserved_memory_max=0.0,
        )

    def _user_extra_arguments(self) -> list[str]:
        """Return free-form args while removing memory args managed by the UI."""
        result: list[str] = []
        index = 0
        values = [str(value) for value in self.extra_arguments]
        while index < len(values):
            token = values[index].strip()
            if not token:
                index += 1
                continue
            if token in self.MANAGED_ARGUMENTS:
                index += 2
                continue
            if any(token.startswith(name + '=') for name in self.MANAGED_ARGUMENTS):
                index += 1
                continue
            result.append(token)
            index += 1
        return result

    def effective_extra_arguments(self) -> list[str]:
        result = self._user_extra_arguments()
        profile = str(self.memory_profile).strip()
        if profile:
            if profile not in {'1', '2', '3', '4', '5'}:
                raise InvalidGenerationRequestError(
                    f'Profilo memoria WanGP non valido: {profile}. Valori ammessi: Auto, 1, 2, 3, 4, 5.'
                )
            result.extend(['--profile', profile])
        reserved = float(self.reserved_memory_max or 0.0)
        if reserved > 0.0:
            reserved = max(0.01, min(1.0, reserved))
            result.extend(['--perc-reserved-mem-max', f'{reserved:.2f}'])
        return result

    def to_video_config(self) -> LocalWanGPConfig:
        return LocalWanGPConfig(
            python_executable=self.python_executable,
            wangp_script=self.wangp_script,
            settings_template=self.settings_template,
            working_directory=self.working_directory,
            verbose=self.verbose,
            strict_python_311=self.strict_python_311,
            require_template=self.require_template,
            process_timeout_seconds=self.process_timeout_seconds,
            extra_arguments=self.effective_extra_arguments(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'LocalWanGPImageConfig':
        try:
            reserved = float(data.get('reserved_memory_max', data.get('perc_reserved_mem_max', 0.0)) or 0.0)
        except (TypeError, ValueError):
            reserved = 0.0
        reserved = max(0.0, min(1.0, reserved))
        return cls(
            python_executable=str(data.get('python_executable', '')),
            wangp_script=str(data.get('wangp_script', '')),
            settings_template=str(data.get('settings_template', '')),
            working_directory=str(data.get('working_directory', '')),
            verbose=max(0, int(data.get('verbose', 2))),
            strict_python_311=bool(data.get('strict_python_311', True)),
            require_template=bool(data.get('require_template', True)),
            process_timeout_seconds=max(0, int(data.get('process_timeout_seconds', 0))),
            extra_arguments=[str(value) for value in data.get('extra_arguments', [])],
            memory_profile=str(data.get('memory_profile', '')).strip(),
            reserved_memory_max=reserved,
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> 'LocalWanGPImageConfig':
        target = Path(path) if path is not None else cls.default_path()
        if target.exists():
            try:
                payload = json.loads(target.read_text(encoding='utf-8'))
                if isinstance(payload, dict):
                    return cls.from_dict(payload)
            except Exception:
                pass
        # Reuse the already configured WanGP runtime, never its video preset.
        return cls.from_video_config(LocalWanGPConfig.load())

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.default_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')
        return target


class WanGPImageSettingsAdapter:
    PLACEHOLDERS = {
        '${JOB_ID}': lambda request, paths: request.job_id,
        '${REFERENCE_IMAGE}': lambda request, paths: paths.get('reference_image'),
        '${POSITIVE_PROMPT}': lambda request, paths: request.positive_prompt,
        '${PROMPT}': lambda request, paths: request.positive_prompt,
        '${NEGATIVE_PROMPT}': lambda request, paths: request.negative_prompt,
        '${SEED}': lambda request, paths: request.seed,
        '${WIDTH}': lambda request, paths: request.width,
        '${HEIGHT}': lambda request, paths: request.height,
        '${STEPS}': lambda request, paths: request.steps,
        '${MODEL}': lambda request, paths: request.model,
        '${OUTPUT_DIR}': lambda request, paths: paths.get('output_directory'),
    }

    def build_payload(
        self,
        request: GenerationRequest,
        config: LocalWanGPImageConfig,
        paths: dict[str, Any],
    ) -> dict[str, Any]:
        template_path = Path(config.settings_template).expanduser() if config.settings_template else None
        if template_path is None or not template_path.is_file():
            raise InvalidGenerationRequestError(
                'R5e9 richiede un preset/settings JSON WanGP dedicato alla generazione immagini.'
            )
        try:
            template = json.loads(template_path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise InvalidGenerationRequestError(f'Preset immagine WanGP non valido: {exc}') from exc
        if not isinstance(template, dict):
            raise InvalidGenerationRequestError('Il preset immagine WanGP deve contenere un oggetto JSON.')
        payload = self._replace(template, request, paths)
        return self._bind_common_fields(payload, request, paths)

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

    @staticmethod
    def _bind_common_fields(
        payload: dict[str, Any],
        request: GenerationRequest,
        paths: dict[str, Any],
    ) -> dict[str, Any]:
        # WanGP exported settings use these keys across the current generation
        # presets. Existing values are intentionally overwritten only for the
        # normalized fields controlled by Sprite Studio.
        payload['prompt'] = request.positive_prompt
        payload['negative_prompt'] = request.negative_prompt
        payload['seed'] = int(request.seed)
        payload['num_inference_steps'] = int(request.steps)
        payload['resolution'] = f'{int(request.width)}x{int(request.height)}'

        reference = paths.get('reference_image')
        if reference:
            # For I2I presets prefer an attachment slot already present in the
            # exported settings. If none is serialized, image_start is the
            # conservative WanGP attachment used by existing I2V/image flows.
            if 'image_refs' in payload and 'image_start' not in payload:
                payload['image_refs'] = [str(reference)]
            else:
                payload['image_start'] = [str(reference)]
        else:
            # Text-to-image must not accidentally retain a stale local path.
            payload.pop('image_start', None)
            if request.task == 'text_to_image':
                payload.pop('image_refs', None)
        return payload


class MockImageProvider(ImageGeneratorProvider):
    provider_id = 'mock_image'
    display_name = 'Development Image Mock'

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            image_to_video=False,
            text_to_image=True,
            image_to_image=True,
            motion_reference=False,
            negative_prompt=True,
            fixed_seed=True,
            cancellation=True,
            progress_reporting=True,
        )

    def validate_request(self, request: GenerationRequest) -> None:
        if request.task not in {'text_to_image', 'image_to_image'}:
            raise InvalidGenerationRequestError('Il mock immagine supporta text_to_image e image_to_image.')
        if request.task == 'image_to_image':
            if not request.reference_image or not Path(request.reference_image).expanduser().is_file():
                raise InvalidGenerationRequestError('Image-to-image richiede un’immagine master valida.')
        if not request.positive_prompt.strip():
            raise InvalidGenerationRequestError('Il prompt positivo non può essere vuoto.')
        if request.width < 64 or request.height < 64:
            raise InvalidGenerationRequestError('Risoluzione minima 64×64.')

    def run(self, request: GenerationRequest, context: GenerationJobContext) -> GenerationResult:
        self.validate_request(request)
        self._check_cancel(context)
        context.progress_callback(GenerationProgress('preprocessing', 0.10, 'Preparazione mock immagine'))
        rng = np.random.default_rng(int(request.seed))
        canvas = np.zeros((request.height, request.width, 3), dtype=np.uint8)
        yy, xx = np.mgrid[:request.height, :request.width]
        canvas[:, :, 0] = np.clip(28 + 60 * xx / max(1, request.width - 1), 0, 255)
        canvas[:, :, 1] = np.clip(38 + 45 * yy / max(1, request.height - 1), 0, 255)
        canvas[:, :, 2] = 52
        noise = rng.normal(0, 2.0, canvas.shape).astype(np.int16)
        canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        reference = None
        if request.reference_image:
            try:
                reference = Image.open(request.reference_image).convert('RGBA')
            except Exception:
                reference = None
        image = Image.fromarray(canvas).convert('RGBA')
        if reference is not None:
            reference.thumbnail((int(request.width * 0.76), int(request.height * 0.76)), Image.Resampling.LANCZOS)
            left = (request.width - reference.width) // 2
            top = (request.height - reference.height) // 2
            image.alpha_composite(reference, (left, top))
        else:
            draw = ImageDraw.Draw(image)
            cx, cy = request.width // 2, int(request.height * 0.48)
            body_w = max(24, request.width // 7)
            body_h = max(54, request.height // 2)
            draw.ellipse((cx-body_w//3, cy-body_h//2, cx+body_w//3, cy-body_h//2+body_w*2//3), fill=(205, 160, 120, 255))
            draw.rounded_rectangle((cx-body_w//2, cy-body_h//4, cx+body_w//2, cy+body_h//3), radius=max(4, body_w//5), fill=(98, 78, 62, 255))
            draw.line((cx-body_w//3, cy+body_h//3, cx-body_w//2, cy+body_h//2), fill=(60, 54, 48, 255), width=max(4, body_w//8))
            draw.line((cx+body_w//3, cy+body_h//3, cx+body_w//2, cy+body_h//2), fill=(60, 54, 48, 255), width=max(4, body_w//8))

        self._check_cancel(context)
        context.progress_callback(GenerationProgress('denoising', 0.75, 'Rendering mock deterministico'))
        output_path = context.output_directory / 'generated_image.png'
        image.save(output_path, format='PNG')
        metadata = {
            'width': request.width,
            'height': request.height,
            'steps': request.steps,
            'task': request.task,
            'mock': True,
            'file_size_bytes': output_path.stat().st_size,
        }
        self._write_image_manifest(request, context, output_path, metadata)
        context.progress_callback(GenerationProgress('saving', 0.99, 'Immagine mock salvata'))
        return GenerationResult(
            job_id=request.job_id,
            state='completed',
            provider=self.provider_id,
            model=request.model,
            video_path=None,
            seed=request.seed,
            image_path=str(output_path),
            metadata=metadata,
        )

    @staticmethod
    def _write_image_manifest(
        request: GenerationRequest,
        context: GenerationJobContext,
        output_path: Path,
        metadata: dict[str, Any],
    ) -> None:
        manifest = {
            'schema': 'unum-sunt-image-generation-manifest-v1',
            'application_version': APP_VERSION,
            'job_id': request.job_id,
            'provider': request.provider,
            'model': request.model,
            'task': request.task,
            'image_path': str(output_path),
            'seed': request.seed,
            'prompt': request.positive_prompt,
            'negative_prompt': request.negative_prompt,
            'width': request.width,
            'height': request.height,
            'steps': request.steps,
            'metadata': metadata,
        }
        (context.job_directory / 'image_generation_manifest.json').write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8'
        )

    @staticmethod
    def _check_cancel(context: GenerationJobContext) -> None:
        if context.cancel_event.is_set():
            raise GenerationCancelledError('Generazione immagine annullata dall’utente.')


class LocalWanGPImageProvider(ImageGeneratorProvider):
    provider_id = 'local_wangp_image'
    display_name = 'Local WAN / WanGP Image Bridge'

    def __init__(self, config: LocalWanGPImageConfig | None = None) -> None:
        self.config = config or LocalWanGPImageConfig.load()
        self.adapter = WanGPImageSettingsAdapter()

    def update_config(self, config: LocalWanGPImageConfig) -> None:
        self.config = config

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            image_to_video=False,
            text_to_image=True,
            image_to_image=True,
            motion_reference=False,
            negative_prompt=True,
            fixed_seed=True,
            cancellation=True,
            progress_reporting=True,
        )

    def health_check(self):
        return LocalWanGPProvider(self.config.to_video_config()).health_check()

    def validate_request(self, request: GenerationRequest) -> None:
        if request.task not in {'text_to_image', 'image_to_image'}:
            raise InvalidGenerationRequestError('Il provider immagine locale supporta text_to_image e image_to_image.')
        if not request.positive_prompt.strip():
            raise InvalidGenerationRequestError('Il prompt positivo non può essere vuoto.')
        if request.width <= 0 or request.height <= 0 or request.steps <= 0:
            raise InvalidGenerationRequestError('Dimensioni e steps devono essere positivi.')
        if request.task == 'image_to_image':
            if not request.reference_image:
                raise InvalidGenerationRequestError('Image-to-image richiede un’immagine master.')
            if not Path(request.reference_image).expanduser().is_file():
                raise InvalidGenerationRequestError(f'Immagine master non trovata: {request.reference_image}')
        report = self.health_check()
        if not report.available:
            raise LocalRuntimeNotInstalledError(report.summary())
        self.adapter.build_payload(
            request,
            self.config,
            {
                'reference_image': request.reference_image,
                'output_directory': '',
            },
        )

    def run(self, request: GenerationRequest, context: GenerationJobContext) -> GenerationResult:
        self.validate_request(request)
        if context.cancel_event.is_set():
            raise GenerationCancelledError('Generazione immagine annullata dall’utente.')
        context.progress_callback(GenerationProgress('validating', 0.02, 'Validazione runtime WanGP Image'))

        reference_path: str | None = None
        if request.reference_image:
            source = Path(request.reference_image).expanduser().resolve()
            target = context.input_directory / source.name
            if source != target:
                shutil.copy2(source, target)
            reference_path = str(target.resolve())

        payload = self.adapter.build_payload(
            request,
            self.config,
            {
                'reference_image': reference_path,
                'output_directory': str(context.output_directory.resolve()),
            },
        )
        settings_path = context.job_directory / 'wangp_image_settings.json'
        settings_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        context.progress_callback(GenerationProgress('starting', 0.05, 'Avvio WanGP image model'))

        runner = LocalWanGPProvider(self.config.to_video_config())
        try:
            runner._run_process(settings_path=settings_path, context=context, dry_run=False)
        except ProcessCrashError as exc:
            detail = str(exc)
            lower = detail.lower()
            if 'out of memory' in lower or 'cudaerrormemoryallocation' in lower:
                raise ProcessCrashError(
                    detail
                    + " | Sprite Studio: memoria esaurita durante Image Gen. "
                      "Prova Memory profile 5 e, se supportato dal runtime WanGP installato, "
                      "Reserved RAM max 0.20; poi prova profilo 4 per maggiore velocità."
                ) from exc
            raise
        if context.cancel_event.is_set():
            raise GenerationCancelledError('Generazione immagine annullata dall’utente.')

        source_output = self._find_output_image(context.output_directory)
        normalized_path = context.output_directory / 'generated_image.png'
        metadata = self._normalize_and_validate_image(source_output, normalized_path)
        metadata.update({
            'task': request.task,
            'steps': request.steps,
            'source_output': str(source_output),
            'settings_file': str(settings_path),
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        })
        MockImageProvider._write_image_manifest(request, context, normalized_path, metadata)
        context.progress_callback(GenerationProgress('saving', 0.995, 'Output immagine WanGP normalizzato'))
        return GenerationResult(
            job_id=request.job_id,
            state='completed',
            provider=self.provider_id,
            model=request.model,
            video_path=None,
            seed=request.seed,
            image_path=str(normalized_path),
            metadata=metadata,
        )

    @staticmethod
    def _find_output_image(output_directory: Path) -> Path:
        candidates = [
            path for path in output_directory.rglob('*')
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and path.name != 'generated_image.png'
            and path.stat().st_size > 0
        ]
        if not candidates:
            # Also accept a provider that already used our normalized filename.
            normalized = output_directory / 'generated_image.png'
            if normalized.is_file() and normalized.stat().st_size > 0:
                return normalized
            raise OutputNotFoundError('WanGP non ha prodotto alcuna immagine leggibile nella cartella output.')
        return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.stat().st_size))

    @staticmethod
    def _normalize_and_validate_image(source: Path, target: Path) -> dict[str, Any]:
        try:
            with Image.open(source) as opened:
                image = opened.convert('RGBA')
                width, height = image.size
                if source.resolve() != target.resolve():
                    image.save(target, format='PNG')
                elif source.suffix.lower() != '.png':
                    image.save(target, format='PNG')
        except Exception as exc:
            raise OutputNotFoundError(f'Output immagine WanGP non leggibile: {exc}') from exc
        if not target.is_file() or target.stat().st_size <= 0:
            raise OutputNotFoundError('Normalizzazione PNG dell’output WanGP fallita.')
        return {
            'width': int(width),
            'height': int(height),
            'file_size_bytes': target.stat().st_size,
            'normalized_format': 'PNG',
        }
