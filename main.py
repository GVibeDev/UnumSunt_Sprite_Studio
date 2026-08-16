from __future__ import annotations

from pathlib import Path
import sys

from app.version import APP_NAME, APP_ORGANIZATION, APP_VERSION


def _argument_value(flag: str) -> str | None:
    try:
        index = sys.argv.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(sys.argv):
        return None
    return sys.argv[index + 1]



def _safe_cli_print(message: str) -> None:
    """Write CLI progress only when a console stream exists.

    PyInstaller --windowed sets stdout/stderr to None; Setup invokes these CLI
    modes from the frozen GUI executable, so progress output must be optional.
    """
    stream = getattr(sys, "stdout", None)
    if stream is None:
        return
    try:
        stream.write(message + "\n")
        stream.flush()
    except Exception:
        pass


def main() -> int:
    if "--version" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    if "--self-check" in sys.argv:
        from app.standalone_selfcheck import run_self_check

        target = _argument_value("--self-check")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "standalone_selfcheck.json")
        return run_self_check(target)

    if "--runtime-preflight" in sys.argv:
        from app.runtime_preflight import RuntimePreflightConfig, STATUS_BLOCKED, run_runtime_preflight

        config = RuntimePreflightConfig.load()
        runtime_root = _argument_value("--runtime-root")
        model_root = _argument_value("--model-root")
        if runtime_root and not runtime_root.startswith("--"):
            config.runtime_root = runtime_root
        if model_root and not model_root.startswith("--"):
            config.model_root = model_root
        target = _argument_value("--runtime-preflight")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "runtime_preflight_R5c3.json")
        report = run_runtime_preflight(config)
        report.save(target)
        config.save()
        return 2 if report.status == STATUS_BLOCKED else 0

    if "--runtime-health" in sys.argv:
        from app.runtime_installer import RuntimeInstaller
        from app.runtime_preflight import RuntimePreflightConfig
        import json

        config = RuntimePreflightConfig.load()
        runtime_root = _argument_value("--runtime-root")
        model_root = _argument_value("--model-root")
        if runtime_root and not runtime_root.startswith("--"):
            config.runtime_root = runtime_root
        if model_root and not model_root.startswith("--"):
            config.model_root = model_root
        report = RuntimeInstaller(config).health_check()
        target = _argument_value("--runtime-health")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "runtime_health_R5c3.json")
        Path(target).write_text(json.dumps({"ready": report.ready, "items": [item.__dict__ for item in report.items]}, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0 if report.ready else 3

    if "--runtime-discover" in sys.argv:
        from app.runtime_adoption import discover_existing_runtimes
        import json

        runtime_root = _argument_value("--runtime-root")
        roots = [runtime_root] if runtime_root and not runtime_root.startswith("--") else []
        candidates = discover_existing_runtimes(extra_roots=roots)
        target = _argument_value("--runtime-discover")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "runtime_discovery_R5c6.json")
        payload = {
            "status": "found" if candidates else "none",
            "candidates": [candidate.__dict__ for candidate in candidates],
        }
        Path(target).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0 if candidates else 5

    if "--runtime-auto-adopt" in sys.argv:
        from app.runtime_adoption import auto_adopt_existing_runtime
        import json

        runtime_root = _argument_value("--runtime-root")
        roots = [runtime_root] if runtime_root and not runtime_root.startswith("--") else []
        target = _argument_value("--runtime-auto-adopt")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "runtime_adoption_R5c6.json")
        state, attempts = auto_adopt_existing_runtime(extra_roots=roots)
        payload = {
            "status": "adopted" if state is not None else "not_found",
            "state": state.__dict__ if state is not None else None,
            "attempts": attempts,
        }
        Path(target).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0 if state is not None else 5

    if "--runtime-install" in sys.argv:
        from app.runtime_installer import RuntimeInstallOptions, RuntimeInstaller
        from app.runtime_preflight import RuntimePreflightConfig
        import json, os

        config = RuntimePreflightConfig.load()
        runtime_root = _argument_value("--runtime-root")
        model_root = _argument_value("--model-root")
        if runtime_root and not runtime_root.startswith("--"):
            config.runtime_root = runtime_root
        if model_root and not model_root.startswith("--"):
            config.model_root = model_root
        options = RuntimeInstallOptions(
            install_runtime="--skip-runtime" not in sys.argv,
            install_wan_animate="--skip-animate" not in sys.argv,
            install_krea2="--skip-krea2" not in sys.argv,
            accept_anaconda_tos="--accept-anaconda-tos" in sys.argv,
            accept_krea_license="--accept-krea-license" in sys.argv,
            hf_token=os.environ.get("HF_TOKEN", ""),
            repair="--repair-runtime" in sys.argv,
        )
        target = _argument_value("--runtime-install")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "runtime_install_R5c3.json")
        try:
            state = RuntimeInstaller(config, progress=lambda phase, fraction, message: _safe_cli_print(f"[{phase}] {fraction:.3f} {message}")).install(options)
            Path(target).write_text(json.dumps(state.__dict__, indent=2, ensure_ascii=False), encoding="utf-8")
            return 0 if state.status in {"ready", "warning"} else 4
        except Exception as exc:
            Path(target).write_text(json.dumps({"status": "failed", "error": str(exc)}, indent=2, ensure_ascii=False), encoding="utf-8")
            return 4

    if "--maintenance-status" in sys.argv:
        from app.maintenance import MaintenanceManager
        import json

        target = _argument_value("--maintenance-status")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "maintenance_status_R5c6.json")
        report = MaintenanceManager().status_report()
        Path(target).write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    if "--maintenance-repair" in sys.argv:
        from app.maintenance import MaintenanceManager
        import json

        target = _argument_value("--maintenance-repair")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "maintenance_repair_R5c6.json")
        try:
            report = MaintenanceManager().repair_managed_runtime(
                accept_anaconda_tos="--accept-anaconda-tos" in sys.argv,
            )
            Path(target).write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            return 0 if report.status in {"ok", "protected"} else 4
        except Exception as exc:
            Path(target).write_text(json.dumps({"status": "failed", "error": str(exc)}, indent=2, ensure_ascii=False), encoding="utf-8")
            return 4

    if "--maintenance-cleanup" in sys.argv:
        from app.maintenance import MaintenanceManager
        import json

        target = _argument_value("--maintenance-cleanup")
        if not target or target.startswith("--"):
            target = str(Path.cwd() / "maintenance_cleanup_R5c6.json")
        try:
            report = MaintenanceManager().cleanup(
                remove_managed_runtime="--remove-managed-runtime" in sys.argv,
                remove_managed_models="--remove-managed-models" in sys.argv,
                remove_user_data="--remove-user-data" in sys.argv,
            )
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            return 0
        except Exception as exc:
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_text(json.dumps({"status": "failed", "error": str(exc)}, indent=2, ensure_ascii=False), encoding="utf-8")
            return 4

    from PySide6.QtWidgets import QApplication
    from app.startup import configure_logging, install_exception_hook
    from app.branding import create_splash_screen, load_app_icon

    configure_logging()
    install_exception_hook()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORGANIZATION)

    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    splash = create_splash_screen()
    if splash is not None:
        splash.show()
        app.processEvents()

    from app.main_window import MainWindow

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()
    if splash is not None:
        splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
