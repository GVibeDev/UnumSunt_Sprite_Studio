from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Mapping

APP_DIR_NAME = "UnumSuntSpriteStudio"


def is_frozen() -> bool:
    """Return True when running from a PyInstaller-frozen executable."""
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    """Directory that contains the executable (or source launcher when unfrozen)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _home(home: str | Path | None) -> Path:
    return Path.home() if home is None else Path(home)


def roaming_config_root(
    *,
    platform_name: str | None = None,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
) -> Path:
    """Persistent user configuration root.

    The path deliberately remains compatible with all R5e builds so upgrading to
    the standalone package does not strand saved profiles or application state.
    """
    platform_name = os.name if platform_name is None else platform_name
    env_map = _environment(env)
    home_path = _home(home)
    if platform_name == "nt":
        base = Path(env_map.get("APPDATA", str(home_path / "AppData" / "Roaming")))
        return base / APP_DIR_NAME
    xdg = env_map.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / APP_DIR_NAME
    return home_path / ".config" / APP_DIR_NAME


def local_data_root(
    *,
    platform_name: str | None = None,
    env: Mapping[str, str] | None = None,
    home: str | Path | None = None,
) -> Path:
    """Writable local-data root for jobs, logs, caches and runtime configuration."""
    platform_name = os.name if platform_name is None else platform_name
    env_map = _environment(env)
    home_path = _home(home)
    if platform_name == "nt":
        base = Path(env_map.get("LOCALAPPDATA", str(home_path / "AppData" / "Local")))
        return base / APP_DIR_NAME
    xdg = env_map.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_DIR_NAME
    return home_path / ".local" / "share" / APP_DIR_NAME


def logs_root() -> Path:
    return local_data_root() / "logs"


def cache_root() -> Path:
    return local_data_root() / "cache"


def generation_jobs_root() -> Path:
    return local_data_root() / "generation_jobs"


def ensure_user_directories() -> dict[str, Path]:
    paths = {
        "config": roaming_config_root(),
        "local_data": local_data_root(),
        "logs": logs_root(),
        "cache": cache_root(),
        "generation_jobs": generation_jobs_root(),
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
