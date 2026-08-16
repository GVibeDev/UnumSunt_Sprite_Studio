from __future__ import annotations

import json
from math import pi, sin
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image

from app.generation.base import GenerationJobContext, VideoGeneratorProvider
from app.generation.errors import (
    GenerationCancelledError,
    InvalidGenerationRequestError,
    OutputNotFoundError,
)
from app.generation.models import (
    GenerationProgress,
    GenerationRequest,
    GenerationResult,
    ProviderCapabilities,
)


class MockVideoProvider(VideoGeneratorProvider):
    provider_id = "mock_video"
    display_name = "Development Mock"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            image_to_video=True,
            motion_reference=False,
            negative_prompt=True,
            fixed_seed=True,
            cancellation=True,
            progress_reporting=True,
            cost_estimation=False,
        )

    def validate_request(self, request: GenerationRequest) -> None:
        if request.task != "image_to_video":
            raise InvalidGenerationRequestError(
                "Il mock R5b supporta soltanto image_to_video."
            )
        if request.width < 96 or request.height < 96:
            raise InvalidGenerationRequestError(
                "La risoluzione minima del mock è 96×96."
            )
        if request.frames < 4 or request.frames > 600:
            raise InvalidGenerationRequestError(
                "Il numero di frame deve essere compreso tra 4 e 600."
            )
        if request.fps <= 0 or request.fps > 120:
            raise InvalidGenerationRequestError("FPS non validi.")

    def run(
        self,
        request: GenerationRequest,
        context: GenerationJobContext,
    ) -> GenerationResult:
        self.validate_request(request)
        context.progress_callback(
            GenerationProgress("validating", 0.03, "Validazione richiesta mock")
        )
        self._check_cancel(context)

        reference_rgba = self._load_reference(request.reference_image)
        context.progress_callback(
            GenerationProgress("preprocessing", 0.10, "Preparazione immagine di riferimento")
        )
        time.sleep(0.08)
        self._check_cancel(context)

        output_path = context.output_directory / "generated_video.mp4"
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            float(request.fps),
            (int(request.width), int(request.height)),
        )
        if not writer.isOpened():
            writer.release()
            raise OutputNotFoundError(
                "OpenCV non è riuscito ad aprire il writer MP4V."
            )

        rng = np.random.default_rng(int(request.seed))
        try:
            for index in range(request.frames):
                self._check_cancel(context)
                phase = index / max(1, request.frames - 1)
                frame = self._render_frame(
                    width=request.width,
                    height=request.height,
                    phase=phase,
                    reference_rgba=reference_rgba,
                    rng=rng,
                    background_rgb=tuple(int(v) for v in request.metadata.get('requested_background_rgb', [20, 218, 90])),
                )
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                fraction = 0.12 + 0.76 * ((index + 1) / request.frames)
                context.progress_callback(
                    GenerationProgress(
                        state="denoising",
                        fraction=fraction,
                        message=f"Simulazione frame {index + 1} di {request.frames}",
                        current_step=index + 1,
                        total_steps=request.frames,
                    )
                )
                time.sleep(0.012)
        finally:
            writer.release()

        self._check_cancel(context)
        context.progress_callback(
            GenerationProgress("decoding", 0.91, "Finalizzazione video simulato")
        )
        time.sleep(0.08)

        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise OutputNotFoundError("Il mock non ha prodotto un MP4 valido.")

        manifest = {
            "schema": "unum-sunt-generation-manifest-v1",
            "job_id": request.job_id,
            "provider": self.provider_id,
            "model": request.model,
            "video_path": str(output_path),
            "seed": request.seed,
            "metadata": {
                "duration": request.frames / request.fps,
                "width": request.width,
                "height": request.height,
                "fps": request.fps,
                "frames": request.frames,
                "mock": True,
                "requested_background_rgb": request.metadata.get('requested_background_rgb'),
                "background_mode": request.metadata.get('background_mode'),
            },
        }
        (context.job_directory / "generation_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        context.progress_callback(
            GenerationProgress("saving", 0.98, "Salvataggio manifest")
        )
        time.sleep(0.05)

        return GenerationResult(
            job_id=request.job_id,
            state="completed",
            provider=self.provider_id,
            model=request.model,
            video_path=str(output_path),
            seed=request.seed,
            metadata=dict(manifest["metadata"]),
        )

    @staticmethod
    def _check_cancel(context: GenerationJobContext) -> None:
        if context.cancel_event.is_set():
            raise GenerationCancelledError("Generazione annullata dall'utente.")

    @staticmethod
    def _load_reference(path_value: str | None) -> np.ndarray | None:
        if not path_value:
            return None
        path = Path(path_value)
        if not path.exists() or not path.is_file():
            return None
        try:
            return np.array(Image.open(path).convert("RGBA"), dtype=np.uint8)
        except Exception:
            return None

    @staticmethod
    def _render_frame(
        *,
        width: int,
        height: int,
        phase: float,
        reference_rgba: np.ndarray | None,
        rng: np.random.Generator,
        background_rgb: tuple[int, int, int],
    ) -> np.ndarray:
        background = np.zeros((height, width, 3), dtype=np.uint8)
        background[:] = tuple(int(max(0, min(255, value))) for value in background_rgb)
        bob = int(round(sin(phase * 2 * pi) * max(2, height * 0.018)))
        sway = int(round(sin(phase * 4 * pi) * max(1, width * 0.009)))

        if reference_rgba is not None:
            subject = reference_rgba
            target_h = max(64, int(height * 0.72))
            scale = min(target_h / subject.shape[0], (width * 0.72) / subject.shape[1])
            target_w = max(1, int(round(subject.shape[1] * scale)))
            target_h = max(1, int(round(subject.shape[0] * scale)))
            subject = cv2.resize(subject, (target_w, target_h), interpolation=cv2.INTER_AREA)
            left = int((width - target_w) / 2 + sway)
            top = int((height - target_h) / 2 + bob)
            MockVideoProvider._composite_rgba(background, subject, left, top)
        else:
            center_x = width // 2 + sway
            ground_y = int(height * 0.84)
            body_h = max(60, int(height * 0.48))
            head_r = max(8, int(body_h * 0.11))
            torso_top = ground_y - body_h + head_r * 2 + bob
            skin = (194, 140, 104)
            cloth = (76, 54, 44)
            accent = (55, 118, 145)
            cv2.circle(background, (center_x, torso_top - head_r), head_r, skin, -1, cv2.LINE_AA)
            cv2.ellipse(background, (center_x, torso_top + body_h // 4), (body_h // 7, body_h // 3), 0, 0, 360, cloth, -1, cv2.LINE_AA)
            arm_phase = sin(phase * 2 * pi)
            leg_phase = sin(phase * 2 * pi + pi)
            shoulder_y = torso_top + body_h // 6
            hip_y = torso_top + body_h // 2
            arm_dx = int(body_h * 0.18 * arm_phase)
            leg_dx = int(body_h * 0.16 * leg_phase)
            cv2.line(background, (center_x - 8, shoulder_y), (center_x - 20 - arm_dx, shoulder_y + body_h // 4), skin, max(4, body_h // 18), cv2.LINE_AA)
            cv2.line(background, (center_x + 8, shoulder_y), (center_x + 20 + arm_dx, shoulder_y + body_h // 4), accent, max(4, body_h // 18), cv2.LINE_AA)
            cv2.line(background, (center_x - 7, hip_y), (center_x - 18 - leg_dx, ground_y + bob), cloth, max(5, body_h // 16), cv2.LINE_AA)
            cv2.line(background, (center_x + 7, hip_y), (center_x + 18 + leg_dx, ground_y + bob), cloth, max(5, body_h // 16), cv2.LINE_AA)
            cv2.ellipse(background, (center_x, torso_top + body_h // 3), (body_h // 4, body_h // 3), -8, 0, 360, (108, 73, 48), 2, cv2.LINE_AA)

        noise = rng.normal(0, 0.6, background.shape).astype(np.int16)
        return np.clip(background.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    @staticmethod
    def _composite_rgba(background: np.ndarray, rgba: np.ndarray, left: int, top: int) -> None:
        h, w = rgba.shape[:2]
        x0 = max(0, left)
        y0 = max(0, top)
        x1 = min(background.shape[1], left + w)
        y1 = min(background.shape[0], top + h)
        if x1 <= x0 or y1 <= y0:
            return
        sx0 = x0 - left
        sy0 = y0 - top
        sx1 = sx0 + (x1 - x0)
        sy1 = sy0 + (y1 - y0)
        source = rgba[sy0:sy1, sx0:sx1]
        alpha = source[:, :, 3:4].astype(np.float32) / 255.0
        target = background[y0:y1, x0:x1].astype(np.float32)
        composed = source[:, :, :3].astype(np.float32) * alpha + target * (1.0 - alpha)
        background[y0:y1, x0:x1] = np.clip(composed, 0, 255).astype(np.uint8)
