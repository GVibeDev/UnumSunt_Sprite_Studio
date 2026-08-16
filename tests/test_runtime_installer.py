from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.runtime_installer import (
    RuntimeInstallOptions,
    RuntimeInstallState,
    RuntimeInstaller,
    RuntimeModelSpec,
    load_runtime_components_manifest,
)
from app.runtime_preflight import RuntimePreflightConfig


class RuntimeInstallerTests(unittest.TestCase):
    def test_manifest_contains_runtime_and_required_models(self):
        manifest = load_runtime_components_manifest()
        self.assertEqual(manifest.python_version, '3.11.14')
        self.assertEqual(manifest.pytorch_version, '2.10.0')
        self.assertEqual(manifest.pytorch_index_url, 'https://download.pytorch.org/whl/cu130')
        self.assertIn('wan_animate', manifest.models)
        self.assertIn('krea2_turbo', manifest.models)
        self.assertFalse(manifest.models['krea2_turbo'].gated)
        self.assertTrue(manifest.models['krea2_turbo'].license_required)
        self.assertEqual(manifest.models['krea2_turbo'].filename, 'Krea2Turbo_quanto_bf16_int8.safetensors')
        self.assertEqual(manifest.models['wan_animate'].sha256, 'c62c8eb97de825ceb66c0e9123b56b2becf5086eb44264ad020b0db6025c6218')

    def test_default_options_do_not_embed_token_persistence(self):
        options = RuntimeInstallOptions(hf_token='hf_secret')
        self.assertEqual(options.hf_token, 'hf_secret')
        state = RuntimeInstallState()
        self.assertNotIn('hf_token', state.__dict__)

    def test_runtime_paths_are_private_under_selected_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RuntimePreflightConfig(str(root/'runtime'), str(root/'models'))
            installer = RuntimeInstaller(config)
            self.assertEqual(installer.miniconda_root, root/'runtime'/'miniconda')
            self.assertEqual(installer.env_root, root/'runtime'/'wangp_env')
            self.assertEqual(installer.wangp_root, root/'runtime'/'WanGP')
            self.assertEqual(installer.ckpts_root, root/'models'/'wangp_ckpts')

    def test_remove_model_deletes_only_selected_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RuntimePreflightConfig(str(root/'runtime'), str(root/'models'))
            installer = RuntimeInstaller(config)
            installer.ckpts_root.mkdir(parents=True)
            target = installer.ckpts_root / installer.manifest.models['wan_animate'].filename
            target.write_bytes(b'test')
            with patch.object(RuntimeInstallState, 'save', return_value=Path(tmp)/'state.json'):
                removed = installer.remove_model('wan_animate')
            self.assertTrue(removed)
            self.assertFalse(target.exists())

    def test_krea_install_requires_license_for_public_wangp_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RuntimePreflightConfig(str(root/'runtime'), str(root/'models'))
            installer = RuntimeInstaller(config)
            fake_python = root/'python.exe'
            fake_python.write_bytes(b'')
            with self.assertRaisesRegex(Exception, 'Community License'):
                installer._install_krea2(fake_python, token='hf_token', accepted=False)
            self.assertFalse(installer.manifest.models['krea2_turbo'].gated)

    def test_windows_miniconda_arguments_do_not_register_python_or_path(self):
        source = Path(__file__).resolve().parents[1] / 'app' / 'runtime_installer.py'
        text = source.read_text(encoding='utf-8')
        self.assertIn('"/RegisterPython=0"', text)
        self.assertIn('"/AddToPath=0"', text)
        self.assertIn('"/InstallationType=JustMe"', text)

    def test_cli_uses_environment_variable_for_hf_token(self):
        source = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')
        self.assertIn('os.environ.get("HF_TOKEN", "")', source)
        self.assertNotIn('--hf-token', source)

    def test_health_optional_components_do_not_block_base_runtime(self):
        from app.runtime_installer import RuntimeHealthItem, RuntimeHealthReport
        items = (
            RuntimeHealthItem('base', True, 'ok', required=True),
            RuntimeHealthItem('cuda.toolkit', False, 'optional', required=False),
            RuntimeHealthItem('model.krea2_turbo', False, 'optional', required=False),
        )
        ready = all(item.ok for item in items if item.required)
        report = RuntimeHealthReport(ready, items)
        self.assertTrue(report.ready)

    def test_runtime_plan_freezes_animate_primary_checkpoint_size(self):
        import json
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root / 'assets' / 'runtime' / 'runtime_install_plan.json').read_text(encoding='utf-8'))
        animate = next(item for item in payload['components'] if item['id'] == 'wan_animate')
        self.assertFalse(animate['estimate'])
        self.assertIn('17,933,520,197', animate['notes'])


if __name__ == '__main__':
    unittest.main()

class RuntimeBridgeBindingHotfixTests(unittest.TestCase):
    def test_sync_bridge_uses_dedicated_wangp_env_not_miniconda_base(self):
        from app.generation.local_wangp import LocalWanGPConfig
        from app.generation.image_provider import LocalWanGPImageConfig
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / 'runtime'
            models = root / 'models'
            python = runtime / 'wangp_env' / 'python.exe'
            wgp = runtime / 'WanGP' / 'wgp.py'
            python.parent.mkdir(parents=True)
            python.write_bytes(b'')
            wgp.parent.mkdir(parents=True)
            wgp.write_text('# test', encoding='utf-8')
            video_path = root / 'local_wangp.json'
            image_path = root / 'local_wangp_image.json'
            with patch.object(LocalWanGPConfig, 'default_path', return_value=video_path), \
                 patch.object(LocalWanGPImageConfig, 'default_path', return_value=image_path):
                installer = RuntimeInstaller(RuntimePreflightConfig(str(runtime), str(models)))
                installer.sync_bridge_configs(validate=False)
                video = LocalWanGPConfig.load(video_path)
                image = LocalWanGPImageConfig.load(image_path)
            self.assertEqual(Path(video.python_executable), python)
            self.assertEqual(Path(image.python_executable), python)
            self.assertNotEqual(Path(video.python_executable), runtime / 'miniconda' / 'python.exe')
            self.assertTrue(video.strict_python_311)

    def test_bridge_validation_rejects_miniconda_base_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / 'runtime'
            models = root / 'models'
            wrong = runtime / 'miniconda' / 'python.exe'
            wrong.parent.mkdir(parents=True)
            wrong.write_bytes(b'')
            installer = RuntimeInstaller(RuntimePreflightConfig(str(runtime), str(models)))
            with self.assertRaisesRegex(Exception, 'ambiente dedicato'):
                installer._validate_bridge_python(wrong)

    def test_generation_workspace_does_not_persist_runtime_config_in_app_state(self):
        source = (Path(__file__).resolve().parents[1] / 'app' / 'generation_workspace.py').read_text(encoding='utf-8')
        snapshot_block = source.split('def snapshot_state(self) -> dict:', 1)[1].split('def apply_state', 1)[0]
        self.assertNotIn("'local_config'", snapshot_block)
        self.assertIn('local_wangp.json is the single source of truth', source)

    def test_local_wangp_health_requires_pytorch_cuda_runtime(self):
        source = (Path(__file__).resolve().parents[1] / 'app' / 'generation' / 'local_wangp.py').read_text(encoding='utf-8')
        self.assertIn("HealthCheckItem('PyTorch runtime'", source)
        self.assertIn('and torch_ok', source)

class R5c3dGpuCapabilityGuardTests(unittest.TestCase):
    def test_runtime_health_has_required_gpu_pytorch_contract(self):
        source = (Path(__file__).resolve().parents[1] / 'app' / 'runtime_installer.py').read_text(encoding='utf-8')
        self.assertIn('"torch.gpu_compatibility"', source)
        self.assertIn('default_device_compatible', source)

    def test_local_wangp_blocks_generation_on_incompatible_torch_architecture(self):
        source = (Path(__file__).resolve().parents[1] / 'app' / 'generation' / 'local_wangp.py').read_text(encoding='utf-8')
        self.assertIn("HealthCheckItem('GPU ↔ PyTorch compatibility'", source)
        self.assertIn('and gpu_compat_ok', source)
