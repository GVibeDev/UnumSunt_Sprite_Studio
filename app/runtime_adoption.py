from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
from typing import Iterable

from app.generation.image_provider import LocalWanGPImageConfig
from app.generation.local_wangp import LocalWanGPConfig, LocalWanGPProvider
from app.runtime_installer import RuntimeInstallState, resolve_wan_animate_settings_template, resolve_krea2_settings_template_for_checkpoint
from app.runtime_preflight import RuntimePreflightConfig


@dataclass(frozen=True)
class ExternalRuntimeCandidate:
    python_executable: str
    wangp_script: str
    working_directory: str
    settings_template: str = ""
    model_root: str = ""
    source: str = "manual"

    @property
    def label(self) -> str:
        python = Path(self.python_executable)
        wgp = Path(self.wangp_script)
        return f"{self.source} · Python: {python.parent} · WanGP: {wgp.parent}"

    def valid_paths(self) -> bool:
        return Path(self.python_executable).is_file() and Path(self.wangp_script).is_file()


def _official_template_or_empty(path: str) -> str:
    candidate = Path(path).expanduser() if path else None
    if candidate is not None and candidate.is_file():
        try:
            import json
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if (
                isinstance(payload, dict)
                and payload.get("model_type")
                and payload.get("model_filename")
                and payload.get("settings_version") is not None
            ):
                return str(candidate)
        except Exception:
            pass
    managed = resolve_wan_animate_settings_template()
    return str(managed) if managed is not None else ""


def candidate_from_current_bridge() -> ExternalRuntimeCandidate | None:
    config = LocalWanGPConfig.load()
    if not config.python_executable or not config.wangp_script:
        return None
    wgp_root = Path(config.working_directory).expanduser() if config.working_directory else Path(config.wangp_script).expanduser().parent
    ckpts = wgp_root / "ckpts"
    candidate = ExternalRuntimeCandidate(
        python_executable=config.python_executable,
        wangp_script=config.wangp_script,
        working_directory=str(wgp_root),
        settings_template=_official_template_or_empty(config.settings_template),
        model_root=str(ckpts if ckpts.exists() else wgp_root),
        source="configurazione bridge corrente",
    )
    return candidate if candidate.valid_paths() else None


def _candidate_from_pair(python: Path, wgp: Path, *, source: str) -> ExternalRuntimeCandidate | None:
    if not python.is_file() or not wgp.is_file():
        return None
    wgp_root = wgp.parent
    model_root = wgp_root / "ckpts"
    return ExternalRuntimeCandidate(
        python_executable=str(python),
        wangp_script=str(wgp),
        working_directory=str(wgp_root),
        settings_template=_official_template_or_empty(""),
        model_root=str(model_root if model_root.exists() else wgp_root),
        source=source,
    )


def discover_existing_runtimes(
    *,
    extra_roots: Iterable[str | Path] = (),
    platform_name: str | None = None,
) -> list[ExternalRuntimeCandidate]:
    """Discover known local layouts without recursively scanning whole drives.

    Discovery is deliberately conservative: current bridge config, configured
    runtime root, and conventional AI roots. It never moves/renames files.
    """
    platform_name = os.name if platform_name is None else platform_name
    found: list[ExternalRuntimeCandidate] = []
    seen: set[tuple[str, str]] = set()

    def add(candidate: ExternalRuntimeCandidate | None) -> None:
        if candidate is None:
            return
        key = (
            str(Path(candidate.python_executable).resolve()).lower(),
            str(Path(candidate.wangp_script).resolve()).lower(),
        )
        if key in seen:
            return
        seen.add(key)
        found.append(candidate)

    add(candidate_from_current_bridge())

    config = RuntimePreflightConfig.load()
    roots: list[Path] = [Path(config.runtime_root).expanduser()]
    roots.extend(Path(value).expanduser() for value in extra_roots)
    if platform_name == "nt":
        # Common locations used by earlier Sprite Studio / WanGP experiments.
        for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            root = Path(f"{drive}:\\AI")
            if root.exists():
                roots.append(root)

    unique_roots: list[Path] = []
    for root in roots:
        if root not in unique_roots and root.exists():
            unique_roots.append(root)

    pairs = (
        (Path("wangp_env") / "python.exe", Path("WanGP") / "wgp.py"),
        (Path("envs") / "WanGP" / "python.exe", Path("WanGP_Standalone") / "wgp.py"),
        (Path("envs") / "WanGP" / "python.exe", Path("WanGP") / "wgp.py"),
        (Path("miniconda") / "envs" / "WanGP" / "python.exe", Path("WanGP") / "wgp.py"),
    )
    for root in unique_roots:
        for python_rel, wgp_rel in pairs:
            add(_candidate_from_pair(root / python_rel, root / wgp_rel, source=f"rilevato in {root}"))
    return found


def validate_external_candidate(candidate: ExternalRuntimeCandidate):
    config = LocalWanGPConfig(
        python_executable=candidate.python_executable,
        wangp_script=candidate.wangp_script,
        settings_template=_official_template_or_empty(candidate.settings_template),
        working_directory=candidate.working_directory or str(Path(candidate.wangp_script).parent),
        verbose=2,
        strict_python_311=True,
        require_template=True,
    )
    return LocalWanGPProvider(config).health_check(), config


def adopt_external_runtime(candidate: ExternalRuntimeCandidate) -> RuntimeInstallState:
    """Register an existing runtime without moving, renaming or downloading it."""
    report, video_config = validate_external_candidate(candidate)
    if not report.available:
        raise RuntimeError("Runtime esterno non adottabile:\n" + report.summary())

    video_config.save()
    image_config = LocalWanGPImageConfig.load()
    image_config.python_executable = video_config.python_executable
    image_config.wangp_script = video_config.wangp_script
    image_config.working_directory = video_config.working_directory
    image_config.strict_python_311 = True
    # Preserve a dedicated image template. If none exists and a current WanGP
    # Krea 2 Turbo checkpoint is already present, bind the managed Krea template
    # without moving or modifying the external model tree.
    if not image_config.settings_template:
        model_root_probe = Path(candidate.model_root).expanduser() if candidate.model_root else Path(video_config.working_directory) / "ckpts"
        # Bind a matching local settings template only when a supported Krea
        # Turbo checkpoint already exists. This may write a tiny settings copy
        # under Sprite Studio user data for full BF16, but never modifies the
        # adopted external runtime or its model tree.
        for name in (
            "Krea2Turbo_quanto_bf16_int8.safetensors",
            "Krea2Turbo_bf16.safetensors",
        ):
            checkpoint = model_root_probe / name
            if checkpoint.is_file():
                image_config.settings_template = str(resolve_krea2_settings_template_for_checkpoint(checkpoint))
                break
    image_config.save()

    python = Path(video_config.python_executable).resolve()
    wgp = Path(video_config.wangp_script).resolve()
    working = Path(video_config.working_directory).resolve()
    model_root = Path(candidate.model_root).expanduser().resolve() if candidate.model_root else working

    state = RuntimeInstallState(
        profile_id="external-wangp",
        status="ready",
        ownership="external",
        updated_at_utc=datetime.now(timezone.utc).isoformat(),
        runtime_root=str(working),
        model_root=str(model_root),
        miniconda_root="",
        env_root=str(python.parent),
        wangp_root=str(wgp.parent),
        python_executable=str(python),
        wangp_script=str(wgp),
        settings_template=video_config.settings_template,
        image_settings_template=image_config.settings_template,
        models={},
        last_error="",
    )
    state.save()

    # Keep the path selector aligned for diagnostics only; adoption never
    # rewrites the external directory structure.
    RuntimePreflightConfig(runtime_root=str(working), model_root=str(model_root)).save()
    return state


def auto_adopt_existing_runtime(
    *,
    extra_roots: Iterable[str | Path] = (),
) -> tuple[RuntimeInstallState | None, list[dict[str, str]]]:
    """Try discovered runtimes in deterministic order and adopt the first healthy one.

    This is intended for the Windows Setup bootstrapper. It is conservative:
    discovery never moves files and failed candidates are only reported.
    """
    attempts: list[dict[str, str]] = []
    for candidate in discover_existing_runtimes(extra_roots=extra_roots):
        try:
            report, _config = validate_external_candidate(candidate)
        except Exception as exc:
            attempts.append({"candidate": candidate.label, "status": "error", "detail": str(exc)})
            continue
        if not report.available:
            attempts.append({"candidate": candidate.label, "status": "not_ready", "detail": report.summary()})
            continue
        try:
            state = adopt_external_runtime(candidate)
        except Exception as exc:
            attempts.append({"candidate": candidate.label, "status": "error", "detail": str(exc)})
            continue
        attempts.append({"candidate": candidate.label, "status": "adopted", "detail": state.runtime_root})
        return state, attempts
    return None, attempts
