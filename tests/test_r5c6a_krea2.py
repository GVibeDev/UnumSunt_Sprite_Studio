from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.generation.image_provider import LocalWanGPImageConfig
from app.generation.local_wangp import LocalWanGPConfig
from app.runtime_installer import RuntimeInstaller, RuntimeInstallError, RuntimeInstallState, load_runtime_components_manifest, resolve_krea2_settings_template_for_checkpoint
from app.runtime_preflight import RuntimePreflightConfig
from app.maintenance import MaintenanceManager


class R5c6aKrea2Tests(unittest.TestCase):
    def test_managed_krea_template_matches_current_wangp_contract(self):
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root / 'assets/runtime/krea2_turbo_settings_template.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['model_type'], 'krea2_turbo')
        self.assertIn('Krea2Turbo_quanto_bf16_int8.safetensors', payload['model_filename'])
        self.assertEqual(payload['num_inference_steps'], 8)
        self.assertEqual(payload['guidance_scale'], 0)
        self.assertEqual(payload['image_mode'], 1)

    def test_manifest_uses_wangp_native_quantized_krea_checkpoint(self):
        spec = load_runtime_components_manifest().models['krea2_turbo']
        self.assertEqual(spec.repo_id, 'DeepBeepMeep/krea-2')
        self.assertEqual(spec.filename, 'Krea2Turbo_quanto_bf16_int8.safetensors')
        self.assertFalse(spec.gated)
        self.assertTrue(spec.license_required)
        self.assertTrue(spec.license_url)
        self.assertTrue(spec.aup_url)

    def test_bridge_sync_binds_krea_image_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / 'runtime'
            models = root / 'models'
            python = runtime / 'wangp_env' / 'python.exe'
            wgp = runtime / 'WanGP' / 'wgp.py'
            python.parent.mkdir(parents=True)
            python.write_bytes(b'')
            (wgp.parent / 'models').mkdir(parents=True)
            wgp.write_text('# test', encoding='utf-8')
            (wgp.parent / 'models' / '_settings.json').write_text('{}', encoding='utf-8')
            video_path = root / 'local_wangp.json'
            image_path = root / 'local_wangp_image.json'
            with patch.object(LocalWanGPConfig, 'default_path', return_value=video_path), \
                 patch.object(LocalWanGPImageConfig, 'default_path', return_value=image_path):
                installer = RuntimeInstaller(RuntimePreflightConfig(str(runtime), str(models)))
                installer.sync_bridge_configs(validate=False)
                image = LocalWanGPImageConfig.load(image_path)
            self.assertTrue(image.settings_template)
            payload = json.loads(Path(image.settings_template).read_text(encoding='utf-8'))
            self.assertEqual(payload['model_type'], 'krea2_turbo')

    def test_existing_krea_checkpoint_is_reused_without_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installer = RuntimeInstaller(RuntimePreflightConfig(str(root/'runtime'), str(root/'models')))
            installer.ckpts_root.mkdir(parents=True)
            target = installer.ckpts_root / 'Krea2Turbo_quanto_bf16_int8.safetensors'
            with target.open('wb') as fh:
                fh.truncate(1024 * 1024 * 1024 + 1)
            fake_python = root / 'python.exe'; fake_python.write_bytes(b'')
            with patch.object(installer, '_run') as run:
                result = installer._install_krea2(fake_python, token='', accepted=True)
            self.assertEqual(result, target)
            run.assert_not_called()


    def test_existing_full_bf16_checkpoint_is_reused_without_quantized_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installer = RuntimeInstaller(RuntimePreflightConfig(str(root/'runtime'), str(root/'models')))
            installer.ckpts_root.mkdir(parents=True)
            target = installer.ckpts_root / 'Krea2Turbo_bf16.safetensors'
            with target.open('wb') as fh:
                fh.truncate(1024 * 1024 * 1024 + 1)
            fake_python = root / 'python.exe'; fake_python.write_bytes(b'')
            with patch.object(installer, '_run') as run:
                result = installer._install_krea2(fake_python, token='', accepted=True)
            self.assertEqual(result, target)
            run.assert_not_called()

    def test_setup_declares_krea_selected_function_and_external_runtime_warning(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / 'installer' / 'UnumSuntSpriteStudio_R5c8.iss').read_text(encoding='utf-8')
        self.assertIn('function KreaSelected: Boolean;', text)
        self.assertIn("WizardIsComponentSelected('ai\\krea2')", text)
        self.assertIn('Adopted and KreaSelected', text)
        self.assertIn('does not modify external runtimes or models', text)


    def test_full_bf16_template_matches_existing_checkpoint_without_model_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = root / 'Krea2Turbo_bf16.safetensors'
            checkpoint.write_bytes(b'fixture')
            with patch('app.runtime_installer.local_data_root', return_value=root / 'userdata'):
                template = resolve_krea2_settings_template_for_checkpoint(checkpoint)
            payload = json.loads(template.read_text(encoding='utf-8'))
            self.assertIn('Krea2Turbo_bf16.safetensors', payload['model_filename'])
            self.assertTrue(checkpoint.is_file())

    def test_reused_krea_checkpoint_is_protected_from_remove_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / 'runtime'; models = root / 'models'
            target = models / 'wangp_ckpts' / 'Krea2Turbo_quanto_bf16_int8.safetensors'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'keep')
            state_path = root / 'state.json'
            state = RuntimeInstallState(
                ownership='managed', runtime_root=str(runtime), model_root=str(models),
                models={'krea2_turbo': {'path': str(target), 'ownership': 'reused'}},
            )
            with patch.object(RuntimeInstallState, 'default_path', return_value=state_path):
                state.save()
                installer = RuntimeInstaller(RuntimePreflightConfig(str(runtime), str(models)))
                with self.assertRaises(RuntimeInstallError):
                    installer.remove_model('krea2_turbo')
            self.assertTrue(target.is_file())

    def test_maintenance_preserves_reused_krea_when_removing_managed_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / 'runtime'; models = root / 'models'; ckpts = models / 'wangp_ckpts'
            ckpts.mkdir(parents=True)
            reused = ckpts / 'Krea2Turbo_quanto_bf16_int8.safetensors'
            managed = ckpts / 'managed-test.safetensors'
            reused.write_bytes(b'keep'); managed.write_bytes(b'delete')
            state = RuntimeInstallState(
                ownership='managed', runtime_root=str(runtime), model_root=str(models),
                models={
                    'krea2_turbo': {'path': str(reused), 'ownership': 'reused'},
                    'managed_fixture': {'path': str(managed), 'ownership': 'managed'},
                },
            )
            state_path = root / 'state.json'
            with patch.object(RuntimeInstallState, 'default_path', return_value=state_path):
                report = MaintenanceManager(state).cleanup(remove_managed_models=True)
            self.assertTrue(reused.is_file())
            self.assertFalse(managed.exists())
            self.assertEqual(report.actions[0].status, 'removed_partial')
            self.assertIn('krea2_turbo', MaintenanceManager(state).state.models)

    def test_state_schema_never_persists_hf_token(self):
        state = RuntimeInstallState(image_settings_template='x')
        self.assertNotIn('hf_token', state.__dict__)

    def test_windows_setup_exposes_krea_component_without_cli_token(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / 'installer' / 'UnumSuntSpriteStudio_R5c8.iss').read_text(encoding='utf-8')
        self.assertIn('ai\\krea2', text)
        self.assertIn('--accept-krea-license', text)
        self.assertIn('--skip-krea2', text)
        self.assertNotIn('--hf-token', text)


if __name__ == '__main__':
    unittest.main()
