from __future__ import annotations

from pathlib import Path

from app.runtime_installer import RuntimeInstaller, RuntimeInstallState
from app.runtime_manager_dialog import RuntimeManagerDialog
from app.runtime_preflight import RuntimePreflightConfig


class RuntimeBridgeController:
    """Keeps managed-runtime persistence separate from MainWindow/app state."""

    def __init__(self, main_window) -> None:
        self.main_window = main_window

    def reload_workspaces(self) -> None:
        self.main_window.generation_workspace.reload_local_runtime_config()
        self.main_window.image_generation_workspace.reload_local_runtime_config()

    def sync_installed_fast(self) -> bool:
        """Repair stale R5c3 bridge paths without importing torch at startup."""
        try:
            state = RuntimeInstallState.load()
            if state.status not in {'ready', 'warning'} or not state.runtime_root or not state.model_root:
                return False
            if state.ownership == 'external':
                expected_python = Path(state.python_executable or (Path(state.env_root) / 'python.exe'))
                expected_wgp = Path(state.wangp_script or (Path(state.wangp_root) / 'wgp.py'))
                if not expected_python.is_file() or not expected_wgp.is_file():
                    return False
                # External/adopted runtimes keep their original folder layout.
                # local_wangp.json is already the binding source of truth; never
                # rewrite it through the managed RuntimeInstaller path model.
                self.reload_workspaces()
                return True

            expected_python = (
                Path(state.python_executable)
                if state.python_executable
                else (Path(state.env_root) / 'python.exe' if state.env_root else Path(state.runtime_root) / 'wangp_env' / 'python.exe')
            )
            expected_wgp = (
                Path(state.wangp_script)
                if state.wangp_script
                else (Path(state.wangp_root) / 'wgp.py' if state.wangp_root else Path(state.runtime_root) / 'WanGP' / 'wgp.py')
            )
            if not expected_python.is_file() or not expected_wgp.is_file():
                return False
            installer = RuntimeInstaller(RuntimePreflightConfig(state.runtime_root, state.model_root))
            installer.sync_bridge_configs(validate=False)
            self.reload_workspaces()
            return True
        except Exception:
            # Startup stays available; Runtime Manager exposes the full diagnostic.
            return False

    def open_manager(self) -> None:
        dialog = RuntimeManagerDialog(self.main_window)
        dialog.runtime_config_changed.connect(self.reload_workspaces)
        dialog.exec()
        self.sync_installed_fast()
        self.reload_workspaces()
