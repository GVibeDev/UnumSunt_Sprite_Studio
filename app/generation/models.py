from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


NORMALIZED_JOB_STATES = (
    "queued",
    "validating",
    "uploading",
    "starting",
    "loading_model",
    "preprocessing",
    "denoising",
    "decoding",
    "downloading",
    "saving",
    "completed",
    "failed",
    "cancelled",
)


@dataclass(frozen=True)
class ProviderCapabilities:
    image_to_video: bool = True
    text_to_image: bool = False
    image_to_image: bool = False
    motion_reference: bool = False
    negative_prompt: bool = True
    fixed_seed: bool = True
    cancellation: bool = True
    progress_reporting: bool = True
    cost_estimation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationRequest:
    job_id: str
    provider: str = "mock_video"
    model: str = "mock_sprite_video_v1"
    task: str = "image_to_video"
    reference_image: str | None = None
    motion_video: str | None = None
    positive_prompt: str = "Character performs a clean animation loop on a flat background."
    negative_prompt: str = "camera movement, scene cuts, changing identity"
    seed: int = 18274
    width: int = 480
    height: int = 480
    frames: int = 49
    fps: float = 24.0
    steps: int = 20
    output_directory: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "task": self.task,
            "provider": self.provider,
            "model": self.model,
            "inputs": {
                "reference_image": self.reference_image,
                "motion_video": self.motion_video,
            },
            "prompt": {
                "positive": self.positive_prompt,
                "negative": self.negative_prompt,
            },
            "generation": {
                "seed": self.seed,
                "width": self.width,
                "height": self.height,
                "frames": self.frames,
                "fps": self.fps,
                "steps": self.steps,
            },
            "output_directory": self.output_directory,
            "metadata": dict(self.metadata),
        }


@dataclass
class GenerationProgress:
    state: str
    fraction: float
    message: str
    current_step: int | None = None
    total_steps: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "fraction": round(max(0.0, min(1.0, float(self.fraction))), 6),
            "message": self.message,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
        }


@dataclass
class GenerationResult:
    job_id: str
    state: str
    provider: str
    model: str
    video_path: str | None
    seed: int
    image_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None

    @property
    def is_completed(self) -> bool:
        return self.state == "completed" and bool(self.video_path or self.image_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "state": self.state,
            "provider": self.provider,
            "model": self.model,
            "video_path": self.video_path,
            "image_path": self.image_path,
            "seed": self.seed,
            "metadata": dict(self.metadata),
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass
class GenerationJobSnapshot:
    job_id: str
    provider: str
    model: str
    state: str
    progress: float
    message: str
    job_directory: str
    result: GenerationResult | None = None
    started_at_utc: str | None = None
    completed_at_utc: str | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "provider": self.provider,
            "model": self.model,
            "state": self.state,
            "progress": round(float(self.progress), 6),
            "message": self.message,
            "job_directory": self.job_directory,
            "result": self.result.to_dict() if self.result else None,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "duration_seconds": None if self.duration_seconds is None else round(float(self.duration_seconds), 6),
        }
