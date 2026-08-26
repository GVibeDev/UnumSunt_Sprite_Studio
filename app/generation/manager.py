from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Event, RLock
import traceback
import time
from typing import Any

from app.generation.base import GenerationJobContext
from app.generation.errors import GenerationCancelledError, GenerationError
from app.generation.models import (
    GenerationJobSnapshot,
    GenerationProgress,
    GenerationRequest,
    GenerationResult,
)
from app.generation.registry import ProviderRegistry
from app.runtime_paths import generation_jobs_root


@dataclass
class _RuntimeJob:
    request: GenerationRequest
    snapshot: GenerationJobSnapshot
    cancel_event: Event
    future: Future | None = None
    started_monotonic: float = 0.0


class GenerationJobManager:
    def __init__(
        self,
        registry: ProviderRegistry,
        workspace_root: str | Path | None = None,
    ) -> None:
        self.registry = registry
        self.workspace_root = Path(workspace_root or self.default_workspace_root()).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="unum-generation")
        self._jobs: dict[str, _RuntimeJob] = {}
        self._lock = RLock()

    @staticmethod
    def default_workspace_root() -> Path:
        return generation_jobs_root()

    def submit(self, request: GenerationRequest) -> str:
        provider = self.registry.get(request.provider)
        provider.validate_request(request)
        job_dir = self.workspace_root / request.job_id
        if job_dir.exists():
            suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            request.job_id = f"{request.job_id}_{suffix}"
            job_dir = self.workspace_root / request.job_id
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        logs_dir = job_dir / "logs"
        for directory in (input_dir, output_dir, logs_dir):
            directory.mkdir(parents=True, exist_ok=True)
        (job_dir / "request.json").write_text(
            json.dumps(request.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        snapshot = GenerationJobSnapshot(
            job_id=request.job_id,
            provider=request.provider,
            model=request.model,
            state="queued",
            progress=0.0,
            message='Job queued',
            job_directory=str(job_dir),
            started_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        runtime = _RuntimeJob(request=request, snapshot=snapshot, cancel_event=Event(), started_monotonic=time.monotonic())
        with self._lock:
            self._jobs[request.job_id] = runtime
            self._write_status(runtime)
            runtime.future = self._executor.submit(self._execute, runtime)
        return request.job_id

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            runtime = self._jobs.get(job_id)
            if runtime is None:
                return False
            if runtime.snapshot.state in {"completed", "failed", "cancelled"}:
                return False
            runtime.cancel_event.set()
            runtime.snapshot.message = 'Cancellation requested'
            self._write_status(runtime)
            return True

    def get_snapshot(self, job_id: str) -> GenerationJobSnapshot | None:
        with self._lock:
            runtime = self._jobs.get(job_id)
            if runtime is None:
                return None
            return GenerationJobSnapshot(
                job_id=runtime.snapshot.job_id,
                provider=runtime.snapshot.provider,
                model=runtime.snapshot.model,
                state=runtime.snapshot.state,
                progress=runtime.snapshot.progress,
                message=runtime.snapshot.message,
                job_directory=runtime.snapshot.job_directory,
                result=runtime.snapshot.result,
                started_at_utc=runtime.snapshot.started_at_utc,
                completed_at_utc=runtime.snapshot.completed_at_utc,
                duration_seconds=runtime.snapshot.duration_seconds,
            )

    def list_snapshots(self) -> list[GenerationJobSnapshot]:
        with self._lock:
            return [self.get_snapshot(job_id) for job_id in self._jobs if self.get_snapshot(job_id) is not None]  # type: ignore[list-item]

    def shutdown(self) -> None:
        with self._lock:
            for runtime in self._jobs.values():
                if runtime.snapshot.state not in {"completed", "failed", "cancelled"}:
                    runtime.cancel_event.set()
        self._executor.shutdown(wait=False, cancel_futures=False)

    @staticmethod
    def _finalize_timing(runtime: _RuntimeJob) -> None:
        runtime.snapshot.completed_at_utc = datetime.now(timezone.utc).isoformat()
        if runtime.started_monotonic > 0:
            runtime.snapshot.duration_seconds = max(0.0, time.monotonic() - runtime.started_monotonic)

    def _execute(self, runtime: _RuntimeJob) -> None:
        request = runtime.request
        provider = self.registry.get(request.provider)
        job_dir = Path(runtime.snapshot.job_directory)
        output_dir = job_dir / "output"
        logs_dir = job_dir / "logs"

        def on_progress(progress: GenerationProgress) -> None:
            with self._lock:
                runtime.snapshot.state = progress.state
                runtime.snapshot.progress = progress.fraction
                runtime.snapshot.message = progress.message
                self._write_status(runtime)

        context = GenerationJobContext(
            job_directory=job_dir,
            input_directory=job_dir / "input",
            output_directory=output_dir,
            logs_directory=logs_dir,
            cancel_event=runtime.cancel_event,
            progress_callback=on_progress,
        )
        try:
            on_progress(GenerationProgress("starting", 0.01, 'Starting provider'))
            result = provider.run(request, context)
            with self._lock:
                runtime.snapshot.state = "completed"
                runtime.snapshot.progress = 1.0
                runtime.snapshot.message = 'Generation completed'
                runtime.snapshot.result = result
                self._finalize_timing(runtime)
                self._write_status(runtime)
                self._write_result(job_dir, result)
        except GenerationCancelledError as exc:
            result = GenerationResult(
                job_id=request.job_id,
                state="cancelled",
                provider=request.provider,
                model=request.model,
                video_path=None,
                seed=request.seed,
                error_code=exc.code,
                error_message=str(exc),
            )
            with self._lock:
                runtime.snapshot.state = "cancelled"
                runtime.snapshot.progress = min(runtime.snapshot.progress, 0.99)
                runtime.snapshot.message = str(exc)
                runtime.snapshot.result = result
                self._finalize_timing(runtime)
                self._write_status(runtime)
                self._write_result(job_dir, result)
        except Exception as exc:
            code = exc.code if isinstance(exc, GenerationError) else "PROVIDER_CRASH"
            error_text = traceback.format_exc()
            (logs_dir / "stderr.log").write_text(error_text, encoding="utf-8")
            result = GenerationResult(
                job_id=request.job_id,
                state="failed",
                provider=request.provider,
                model=request.model,
                video_path=None,
                seed=request.seed,
                error_code=code,
                error_message=str(exc),
            )
            with self._lock:
                runtime.snapshot.state = "failed"
                runtime.snapshot.message = str(exc)
                runtime.snapshot.result = result
                self._finalize_timing(runtime)
                self._write_status(runtime)
                self._write_result(job_dir, result)

    @staticmethod
    def _write_result(job_dir: Path, result: GenerationResult) -> None:
        (job_dir / "manifest.json").write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _write_status(runtime: _RuntimeJob) -> None:
        path = Path(runtime.snapshot.job_directory) / "status.json"
        payload: dict[str, Any] = runtime.snapshot.to_dict()
        payload["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
