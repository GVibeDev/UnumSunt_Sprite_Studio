from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.maintenance import MaintenanceManager
from app.runtime_installer import RuntimeInstallState


class MaintenanceR5c6aTests(unittest.TestCase):
    def test_external_runtime_is_never_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = root / "external_runtime"
            models = root / "external_models"
            runtime.mkdir()
            models.mkdir()
            (runtime / "keep.txt").write_text("runtime")
            (models / "keep.txt").write_text("models")
            state = RuntimeInstallState(
                ownership="external",
                status="ready",
                runtime_root=str(runtime),
                model_root=str(models),
            )
            with patch.object(RuntimeInstallState, "save", return_value=Path(td) / "state.json"):
                report = MaintenanceManager(state).cleanup(
                    remove_managed_runtime=True,
                    remove_managed_models=True,
                )
            self.assertTrue(runtime.exists())
            self.assertTrue(models.exists())
            self.assertTrue(any(action.status == "protected" for action in report.actions))

    def test_managed_model_cleanup_only_removes_wangp_ckpts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = root / "runtime"
            model_root = root / "models"
            ckpts = model_root / "wangp_ckpts"
            unrelated = model_root / "unrelated.txt"
            runtime.mkdir()
            ckpts.mkdir(parents=True)
            (ckpts / "animate.safetensors").write_bytes(b"checkpoint")
            unrelated.write_text("keep")
            state = RuntimeInstallState(
                ownership="managed", status="ready",
                runtime_root=str(runtime), model_root=str(model_root),
                models={"wan_animate": {"status": "installed"}},
            )
            with patch.object(RuntimeInstallState, "save", return_value=root / "state.json"):
                MaintenanceManager(state).cleanup(remove_managed_models=True)
            self.assertFalse(ckpts.exists())
            self.assertTrue(unrelated.is_file())
            self.assertTrue(runtime.exists())

    def test_managed_runtime_can_be_removed_while_models_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = root / "runtime"
            ckpts = root / "models" / "wangp_ckpts"
            runtime.mkdir()
            ckpts.mkdir(parents=True)
            (runtime / "wgp.py").write_text("# mock")
            (ckpts / "model.bin").write_bytes(b"model")
            state = RuntimeInstallState(
                ownership="managed", status="ready",
                runtime_root=str(runtime), model_root=str(root / "models"),
            )
            with patch.object(RuntimeInstallState, "save", return_value=root / "state.json"):
                manager = MaintenanceManager(state)
                manager.cleanup(remove_managed_runtime=True, remove_managed_models=False)
            self.assertFalse(runtime.exists())
            self.assertTrue((ckpts / "model.bin").is_file())
            self.assertEqual(manager.state.status, "runtime_removed")

    def test_user_data_purge_keeps_runtime_registry_when_runtime_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            local = root / "local" / "UnumSuntSpriteStudio"
            roaming = root / "roaming" / "UnumSuntSpriteStudio"
            runtime = local / "ai_runtime"
            models = root / "models"
            runtime.mkdir(parents=True)
            models.mkdir()
            logs = local / "logs"; logs.mkdir(parents=True)
            cache = local / "cache"; cache.mkdir()
            jobs = local / "generation_jobs"; jobs.mkdir()
            setup = local / "setup"; setup.mkdir()
            video_cfg = local / "local_wangp.json"; video_cfg.write_text("{}")
            image_cfg = local / "local_wangp_image.json"; image_cfg.write_text("{}")
            preflight_cfg = local / "runtime_preflight_config.json"; preflight_cfg.write_text("{}")
            state_path = local / "runtime_install_state.json"; state_path.write_text("{}")
            roaming.mkdir(parents=True)
            (roaming / "profiles.json").write_text("{}")
            state = RuntimeInstallState(
                ownership="managed", status="ready",
                runtime_root=str(runtime), model_root=str(models),
            )
            with patch('app.maintenance.local_data_root', return_value=local), \
                 patch('app.maintenance.roaming_config_root', return_value=roaming), \
                 patch('app.maintenance.logs_root', return_value=logs), \
                 patch('app.maintenance.cache_root', return_value=cache), \
                 patch('app.maintenance.generation_jobs_root', return_value=jobs), \
                 patch('app.maintenance.LocalWanGPConfig.default_path', return_value=video_cfg), \
                 patch('app.maintenance.LocalWanGPImageConfig.default_path', return_value=image_cfg), \
                 patch('app.maintenance.RuntimePreflightConfig.default_path', return_value=preflight_cfg), \
                 patch('app.maintenance.RuntimeInstallState.default_path', return_value=state_path), \
                 patch.object(RuntimeInstallState, "save", return_value=state_path):
                MaintenanceManager(state).cleanup(remove_user_data=True)
            self.assertTrue(runtime.exists())
            self.assertTrue(video_cfg.exists())
            self.assertTrue(image_cfg.exists())
            self.assertTrue(preflight_cfg.exists())
            self.assertFalse(roaming.exists())
            self.assertFalse(logs.exists())
            self.assertFalse(cache.exists())
            self.assertFalse(jobs.exists())

    def test_external_runtime_repair_is_protected(self) -> None:
        state = RuntimeInstallState(ownership="external", status="ready", runtime_root="X:/WanGP")
        report = MaintenanceManager(state).repair_managed_runtime()
        self.assertEqual(report.status, "protected")
        self.assertEqual(report.actions[0].status, "skipped")

    def test_status_report_exposes_ownership(self) -> None:
        state = RuntimeInstallState(ownership="external", status="ready", runtime_root="X:/WanGP")
        report = MaintenanceManager(state).status_report()
        self.assertEqual(report.ownership, "external")
        self.assertTrue(any("esterno" in warning.lower() for warning in report.warnings))

    def test_setup_preserves_same_app_id_and_supports_cleanup_choices(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = (root / "installer" / "UnumSuntSpriteStudio_R5c6a.iss").read_text(encoding="utf-8")
        self.assertIn("AppId={{5F2F2D9A-6C3C-4D0A-A0D4-2D9EF36D5D42}", script)
        self.assertIn("UsePreviousAppDir=yes", script)
        self.assertIn("--maintenance-cleanup", script)
        self.assertIn("--remove-managed-runtime", script)
        self.assertIn("--remove-managed-models", script)
        self.assertIn("--remove-user-data", script)
        self.assertIn("CurUninstallStepChanged", script)

    def test_setup_persists_paths_but_not_legal_acceptance(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = (root / "installer" / "UnumSuntSpriteStudio_R5c6a.iss").read_text(encoding="utf-8")
        self.assertIn("RegisterPreviousData", script)
        self.assertIn("SetPreviousData(PreviousDataKey, 'RuntimeRoot'", script)
        self.assertIn("SetPreviousData(PreviousDataKey, 'ModelRoot'", script)
        self.assertIn("GetPreviousData('RuntimeRoot'", script)
        self.assertIn("Legal acceptance is deliberately never persisted", script)
        self.assertNotIn("SetPreviousData(PreviousDataKey, 'Accept", script)

    def test_main_exposes_r5c6_maintenance_cli(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "main.py").read_text(encoding="utf-8")
        self.assertIn('"--maintenance-status"', text)
        self.assertIn('"--maintenance-repair"', text)
        self.assertIn('"--maintenance-cleanup"', text)
        self.assertIn('"--remove-managed-runtime"', text)
        self.assertIn('"--remove-managed-models"', text)
        self.assertIn('"--remove-user-data"', text)

    def test_build_script_targets_r5c6_setup(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "build_setup_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("installer\\UnumSuntSpriteStudio_R5c6a.iss", text)
        self.assertIn("UnumSunt_Sprite_Studio_R5c6a_Setup_x64.exe", text)


if __name__ == "__main__":
    unittest.main()
