from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any

from app.runtime_paths import ensure_user_directories, executable_dir, is_frozen
from app.version import APP_NAME, APP_VERSION

CORE_MODULES = ("numpy", "cv2", "PIL", "PySide6")


def _module_version(module: Any) -> str | None:
    value = getattr(module, "__version__", None)
    if value is None and getattr(module, "VERSION", None) is not None:
        value = getattr(module, "VERSION")
    return str(value) if value is not None else None


def build_self_check_payload(*, import_runtime: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    dependencies: dict[str, str | None] = {}
    ok = True

    try:
        directories = ensure_user_directories()
        writable_paths: dict[str, str] = {}
        for name, directory in directories.items():
            probe = directory / ".r5c2_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            writable_paths[name] = str(directory)
        checks.append({"name": "user_directories", "ok": True, "detail": writable_paths})
    except Exception as exc:
        ok = False
        checks.append({"name": "user_directories", "ok": False, "detail": repr(exc)})

    if import_runtime:
        for module_name in CORE_MODULES:
            try:
                module = importlib.import_module(module_name)
                dependencies[module_name] = _module_version(module)
                checks.append({"name": f"import:{module_name}", "ok": True, "detail": dependencies[module_name]})
            except Exception as exc:
                ok = False
                checks.append({"name": f"import:{module_name}", "ok": False, "detail": repr(exc)})
        try:
            importlib.import_module("app.main_window")
            checks.append({"name": "import:app.main_window", "ok": True, "detail": "loaded"})
        except Exception as exc:
            ok = False
            checks.append({"name": "import:app.main_window", "ok": False, "detail": repr(exc)})
        try:
            from app.runtime_preflight import load_install_plan
            plan = load_install_plan()
            checks.append({"name": "runtime_preflight_plan", "ok": True, "detail": plan.profile_id})
        except Exception as exc:
            ok = False
            checks.append({"name": "runtime_preflight_plan", "ok": False, "detail": repr(exc)})

    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "status": "passed" if ok else "failed",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen": is_frozen(),
        "python": sys.version,
        "python_executable": sys.executable,
        "executable_dir": str(executable_dir()),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "is_64_bit_process": sys.maxsize > 2**32,
        "dependencies": dependencies,
        "checks": checks,
        "ai_runtime": {
            "bundled": False,
            "status": "external_managed",
            "note": f"WanGP/Miniconda/PyTorch/models are external to the Core bundle and managed by the {APP_VERSION} Runtime Manager.",
        },
    }


def run_self_check(target: str | Path, *, import_runtime: bool = True) -> int:
    path = Path(target).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_self_check_payload(import_runtime=import_runtime)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if payload["status"] == "passed" else 2
