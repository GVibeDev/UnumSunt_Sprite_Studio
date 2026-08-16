from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from app.generation.models import (
    GenerationProgress,
    GenerationRequest,
    GenerationResult,
    ProviderCapabilities,
)


ProgressCallback = Callable[[GenerationProgress], None]


@dataclass(frozen=True)
class GenerationJobContext:
    job_directory: Path
    input_directory: Path
    output_directory: Path
    logs_directory: Path
    cancel_event: Event
    progress_callback: ProgressCallback


class MediaGeneratorProvider(ABC):
    """Common contract for local/remote media generators.

    R5e9 introduces image generation without coupling the existing video
    pipeline to a specific runtime. Video and image providers share the same
    normalized request/result/job machinery while retaining distinct provider
    contracts.
    """

    provider_id: str
    display_name: str

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    @abstractmethod
    def validate_request(self, request: GenerationRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    def run(
        self,
        request: GenerationRequest,
        context: GenerationJobContext,
    ) -> GenerationResult:
        raise NotImplementedError


class VideoGeneratorProvider(MediaGeneratorProvider):
    """Marker contract for video-producing providers."""


class ImageGeneratorProvider(MediaGeneratorProvider):
    """Marker contract for still-image providers."""
