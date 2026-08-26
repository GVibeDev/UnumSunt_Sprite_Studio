from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from app.generation.image_provider import LocalWanGPImageConfig
from app.generation.local_wangp import LocalWanGPConfig
from app.runtime_installer import RuntimeInstallOptions, RuntimeInstallState, RuntimeInstaller
from app.runtime_paths import cache_root, generation_jobs_root, local_data_root, logs_root, roaming_config_root
from app.runtime_preflight import RuntimePreflightConfig


MAINTENANCE_SCHEMA = "unum-sunt-maintenance-v1"


class MaintenanceError(RuntimeError):
    pass


@dataclass
class MaintenanceAction:
    id: str
    status: str
    detail: str


@dataclass
class MaintenanceReport:
    schema: str = MAINTENANCE_SCHEMA
    status: str = "ok"
    created_at_utc: str = ""
    ownership: str = "unknown"
    runtime_root: str = ""
    model_root: str = ""
    actions: list[MaintenanceAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "created_at_utc": self.created_at_utc,
            "ownership": self.ownership,
            "runtime_root": self.runtime_root,
            "model_root": self.model_root,
            "actions": [asdict(item) for item in self.actions],
            "warnings": list(self.warnings),
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return target


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_managed_target(path: Path) -> bool:
    """Reject catastrophic deletion targets while allowing custom managed roots."""
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        return False
    if not str(resolved).strip():
        return False
    if resolved == Path(resolved.anchor):
        return False
    if resolved == Path.home().resolve():
        return False
    # C:\Users\name or /home/name descendants are fine, but never delete the
    # whole local-data parent itself by accident.
    local_parent = local_data_root().resolve().parent
    if resolved == local_parent:
        return False
    return len(resolved.parts) >= 3


def _is_junction(path: Path) -> bool:
    method = getattr(path, "is_junction", None)
    if callable(method):
        try:
            return bool(method())
        except OSError:
            return False
    return False


def _delete_tree(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_symlink() or _is_junction(path):
        path.unlink(missing_ok=True)
        return True
    if path.is_dir():
        shutil.rmtree(path)
        return True
    path.unlink(missing_ok=True)
    return True


def _remove_if_exists(path: Path) -> bool:
    try:
        return _delete_tree(path)
    except FileNotFoundError:
        return False


class MaintenanceManager:
    """Lifecycle maintenance for the installed Core and managed AI runtime.

    External/adopted runtimes are always read-only from maintenance.  Managed
    model cleanup is intentionally limited to ``<model_root>/wangp_ckpts`` so a
    user-selected model disk can contain unrelated files safely.
    """

    def __init__(self, state: RuntimeInstallState | None = None) -> None:
        self.state = state or RuntimeInstallState.load()

    def status_report(self) -> MaintenanceReport:
        state = self.state
        report = MaintenanceReport(
            created_at_utc=_now(),
            ownership=state.ownership or "unknown",
            runtime_root=state.runtime_root,
            model_root=state.model_root,
        )
        runtime = Path(state.runtime_root).expanduser() if state.runtime_root else None
        model_root = Path(state.model_root).expanduser() if state.model_root else None
        report.actions.append(MaintenanceAction(
            "runtime.present",
            "present" if runtime is not None and runtime.exists() else "missing",
            str(runtime or ""),
        ))
        ckpts = model_root / "wangp_ckpts" if model_root else None
        report.actions.append(MaintenanceAction(
            "models.present",
            "present" if ckpts is not None and ckpts.exists() else "missing",
            str(ckpts or ""),
        ))
        if state.ownership == "external":
            report.warnings.append('External/adopted runtime: destructive repair and delete operations are disabled.')
        return report

    def repair_managed_runtime(self, *, accept_anaconda_tos: bool = False) -> MaintenanceReport:
        state = self.state
        report = MaintenanceReport(
            created_at_utc=_now(), ownership=state.ownership or "unknown",
            runtime_root=state.runtime_root, model_root=state.model_root,
        )
        if state.ownership != "managed":
            report.status = "protected"
            report.actions.append(MaintenanceAction(
                "runtime.repair", "skipped",
                'External/adopted runtime: no changes made.',
            ))
            return report

        config = RuntimePreflightConfig.load()
        if state.runtime_root:
            config.runtime_root = state.runtime_root
        if state.model_root:
            config.model_root = state.model_root
        installer = RuntimeInstaller(config)
        result = installer.install(RuntimeInstallOptions(
            install_runtime=True,
            install_wan_animate=False,
            install_krea2=False,
            accept_anaconda_tos=accept_anaconda_tos,
            repair=True,
        ))
        self.state = result
        report.runtime_root = result.runtime_root
        report.model_root = result.model_root
        report.actions.append(MaintenanceAction(
            "runtime.repair", result.status,
            'Base runtime repaired/updated; existing checkpoints preserved.',
        ))
        report.status = "ok" if result.status in {"ready", "warning"} else result.status
        return report

    def cleanup(
        self,
        *,
        remove_managed_runtime: bool = False,
        remove_managed_models: bool = False,
        remove_user_data: bool = False,
    ) -> MaintenanceReport:
        state = self.state
        report = MaintenanceReport(
            created_at_utc=_now(), ownership=state.ownership or "unknown",
            runtime_root=state.runtime_root, model_root=state.model_root,
        )

        if state.ownership == "external" and (remove_managed_runtime or remove_managed_models):
            report.warnings.append(
                'External/adopted runtime protected: no external WanGP folder or model was deleted.'
            )
            if remove_managed_runtime:
                report.actions.append(MaintenanceAction("runtime.remove", "protected", state.runtime_root))
            if remove_managed_models:
                report.actions.append(MaintenanceAction("models.remove", "protected", state.model_root))
        elif state.ownership == "managed":
            runtime_root = Path(state.runtime_root).expanduser() if state.runtime_root else None
            model_root = Path(state.model_root).expanduser() if state.model_root else None
            ckpts_root = model_root / "wangp_ckpts" if model_root else None

            if remove_managed_models:
                if ckpts_root is None or not _safe_managed_target(ckpts_root):
                    raise MaintenanceError(f'Unsafe checkpoint path: {ckpts_root}')
                reused_records = {
                    model_id: record for model_id, record in state.models.items()
                    if isinstance(record, dict) and str(record.get("ownership", "")).lower() in {"reused", "external"}
                }
                if reused_records:
                    # A managed model root may contain a checkpoint that existed
                    # before Sprite Studio adopted it (notably Krea 2). In that
                    # case never delete the whole tree: remove only files that
                    # the install state explicitly owns, preserving reused and
                    # unknown/shared assets.
                    removed_any = False
                    for model_id, record in list(state.models.items()):
                        if model_id in reused_records or not isinstance(record, dict):
                            continue
                        raw_path = str(record.get("path", ""))
                        if not raw_path:
                            continue
                        candidate = Path(raw_path).expanduser()
                        try:
                            candidate_resolved = candidate.resolve()
                            ckpts_resolved = ckpts_root.resolve()
                            candidate_resolved.relative_to(ckpts_resolved)
                        except Exception:
                            report.warnings.append(f'Managed checkpoint outside the expected root, preserved: {candidate}')
                            continue
                        if candidate.is_file():
                            candidate.unlink()
                            removed_any = True
                        state.models.pop(model_id, None)
                    report.actions.append(MaintenanceAction(
                        "models.remove", "removed_partial" if removed_any else "preserved", str(ckpts_root)
                    ))
                    report.warnings.append(
                        'Pre-existing/reused checkpoints detected: the wangp_ckpts folder was preserved and only explicitly managed models were removed.'
                    )
                else:
                    removed = _remove_if_exists(ckpts_root)
                    state.models.clear()
                    report.actions.append(MaintenanceAction(
                        "models.remove", "removed" if removed else "already_missing", str(ckpts_root)
                    ))

            if remove_managed_runtime:
                if runtime_root is None or not _safe_managed_target(runtime_root):
                    raise MaintenanceError(f'Unsafe runtime path: {runtime_root}')
                removed = _remove_if_exists(runtime_root)
                report.actions.append(MaintenanceAction(
                    "runtime.remove", "removed" if removed else "already_missing", str(runtime_root)
                ))
                state.status = "runtime_removed"
                state.python_executable = ""
                state.wangp_script = ""
                state.settings_template = ""
                state.image_settings_template = ""
                state.miniconda_root = ""
                state.env_root = ""
                state.wangp_root = ""
        elif remove_managed_runtime or remove_managed_models:
            report.warnings.append('No managed runtime registered: nothing to remove.')

        if remove_user_data:
            self._purge_user_data(
                report,
                preserve_runtime=(state.ownership == "managed" and not remove_managed_runtime),
                preserve_models=(state.ownership == "managed" and not remove_managed_models),
            )

        state.updated_at_utc = _now()
        if remove_user_data:
            # Purge may remove the normal state location. Recreate the state only
            # when a managed runtime/model tree has deliberately been preserved,
            # so a future reinstall can rediscover it without downloads.
            if (
                state.ownership == "managed"
                and ((not remove_managed_runtime and state.runtime_root) or (not remove_managed_models and state.model_root))
            ):
                state.save()
        else:
            state.save()
        self.state = state
        return report

    def _purge_user_data(self, report: MaintenanceReport, *, preserve_runtime: bool, preserve_models: bool) -> None:
        # Projects are never stored/removed by this routine; only application
        # config, logs, cache and temporary generation jobs are targeted.
        roaming = roaming_config_root()
        if _safe_managed_target(roaming):
            removed = _remove_if_exists(roaming)
            report.actions.append(MaintenanceAction(
                "userdata.roaming", "removed" if removed else "already_missing", str(roaming)
            ))

        local = local_data_root()
        transient = [logs_root(), cache_root(), generation_jobs_root(), local / "setup"]
        config_files: list[Path] = []
        if not preserve_runtime:
            config_files.extend([
                LocalWanGPConfig.default_path(),
                LocalWanGPImageConfig.default_path(),
            ])
        # Keep the path registry whenever runtime or checkpoints are preserved,
        # otherwise a custom location could become undiscoverable after reinstall.
        if not preserve_runtime and not preserve_models:
            config_files.extend([
                RuntimePreflightConfig.default_path(),
                RuntimeInstallState.default_path(),
            ])

        for target in transient:
            if _safe_managed_target(target):
                removed = _remove_if_exists(target)
                report.actions.append(MaintenanceAction(
                    "userdata.local", "removed" if removed else "already_missing", str(target)
                ))
        for target in config_files:
            existed = target.exists()
            try:
                target.unlink(missing_ok=True)
            except OSError as exc:
                report.warnings.append(f'Unable to remove {target}: {exc}')
                continue
            report.actions.append(MaintenanceAction(
                "userdata.config", "removed" if existed else "already_missing", str(target)
            ))

        if preserve_runtime:
            report.warnings.append('Managed runtime preserved while cleaning application data.')
        if preserve_models:
            report.warnings.append('Managed checkpoints preserved while cleaning application data.')
