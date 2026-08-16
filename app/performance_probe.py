from __future__ import annotations

import atexit
import json
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar


F = TypeVar('F', bound=Callable[..., Any])


def _env_enabled() -> bool:
    value = os.getenv('UNUM_SUNT_PERF', '').strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


@dataclass
class _Metric:
    samples_ms: list[float] = field(default_factory=list)
    total_ms: float = 0.0
    max_ms: float = 0.0

    def add(self, elapsed_ms: float, *, sample_limit: int) -> None:
        self.total_ms += elapsed_ms
        self.max_ms = max(self.max_ms, elapsed_ms)
        self.samples_ms.append(elapsed_ms)
        if len(self.samples_ms) > sample_limit:
            del self.samples_ms[: len(self.samples_ms) - sample_limit]


class PerformanceProbe:
    """Low-overhead opt-in timing collector for R5e13b profiling.

    Disabled by default. Set UNUM_SUNT_PERF=1 before launching the application to
    collect timings. No file is written automatically; callers explicitly request
    a snapshot/report so normal application behaviour remains unchanged.
    """

    def __init__(self, *, enabled: bool | None = None, sample_limit: int = 2048) -> None:
        self.enabled = _env_enabled() if enabled is None else bool(enabled)
        self.sample_limit = max(16, int(sample_limit))
        self._metrics: dict[str, _Metric] = {}
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._metrics.clear()
            self._counts.clear()

    def record(self, name: str, elapsed_ms: float) -> None:
        if not self.enabled:
            return
        key = str(name)
        with self._lock:
            metric = self._metrics.setdefault(key, _Metric())
            metric.add(float(elapsed_ms), sample_limit=self.sample_limit)
            self._counts[key] = self._counts.get(key, 0) + 1

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        start = time.perf_counter_ns()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000.0
            self.record(name, elapsed_ms)

    def instrument(self, name: str) -> Callable[[F], F]:
        def decorator(function: F) -> F:
            @wraps(function)
            def wrapper(*args: Any, **kwargs: Any):
                if not self.enabled:
                    return function(*args, **kwargs)
                with self.measure(name):
                    return function(*args, **kwargs)
            return wrapper  # type: ignore[return-value]
        return decorator

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            result: dict[str, Any] = {
                'enabled': self.enabled,
                'sample_limit': self.sample_limit,
                'metrics': {},
            }
            for name in sorted(self._metrics):
                metric = self._metrics[name]
                samples = list(metric.samples_ms)
                count = self._counts.get(name, len(samples))
                ordered = sorted(samples)
                if ordered:
                    p95_index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * 0.95))))
                    mean_ms = (metric.total_ms / count) if count else 0.0
                    p95_ms = ordered[p95_index]
                else:
                    mean_ms = 0.0
                    p95_ms = 0.0
                result['metrics'][name] = {
                    'count': count,
                    'sample_count': len(samples),
                    'total_ms': round(metric.total_ms, 6),
                    'mean_ms': round(mean_ms, 6),
                    'max_ms': round(metric.max_ms, 6),
                    'p95_ms': round(p95_ms, 6),
                }
            return result

    def write_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.snapshot(), indent=2, ensure_ascii=False), encoding='utf-8')
        return target


performance_probe = PerformanceProbe()
perf_instrument = performance_probe.instrument

_report_path = os.getenv('UNUM_SUNT_PERF_REPORT', '').strip()
if performance_probe.enabled and _report_path:
    atexit.register(lambda: performance_probe.write_json(_report_path))
