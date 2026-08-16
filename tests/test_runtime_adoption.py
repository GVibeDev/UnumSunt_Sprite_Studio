from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from app.generation.image_provider import LocalWanGPImageConfig
from app.generation.local_wangp import LocalWanGPConfig, LocalWanGPProvider
from app.runtime_adoption import ExternalRuntimeCandidate, adopt_external_runtime, discover_existing_runtimes
from app.runtime_installer import RuntimeInstallState
from app.runtime_preflight import RuntimePreflightConfig


class RuntimeAdoptionTests(unittest.TestCase):
    def test_development_bridge_does_not_require_torch_when_python311_guard_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mock = root / 'mock_wangp_cli.py'
            mock.write_text('print("ok")', encoding='utf-8')
            provider = LocalWanGPProvider(LocalWanGPConfig(
                python_executable=__import__('sys').executable,
                wangp_script=str(mock),
                working_directory=str(root),
                strict_python_311=False,
                require_template=False,
            ))
            report = provider.health_check()
            self.assertTrue(report.available, report.summary())
            self.assertFalse(any(item.name == 'PyTorch runtime' for item in report.checks))
            self.assertTrue(any('development/mock' in warning for warning in report.warnings))

    def test_discovery_finds_legacy_ai_layout_without_renaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai = Path(tmp) / 'AI'
            python = ai / 'envs' / 'WanGP' / 'python.exe'
            wgp = ai / 'WanGP_Standalone' / 'wgp.py'
            python.parent.mkdir(parents=True)
            wgp.parent.mkdir(parents=True)
            python.write_bytes(b'')
            wgp.write_text('# fixture', encoding='utf-8')
            candidates = discover_existing_runtimes(extra_roots=[ai], platform_name='posix')
            matches = [c for c in candidates if Path(c.python_executable) == python and Path(c.wangp_script) == wgp]
            self.assertEqual(len(matches), 1)
            self.assertTrue(python.exists())
            self.assertTrue(wgp.exists())

    def test_adoption_persists_explicit_external_paths_and_never_moves_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = root / 'envs' / 'WanGP' / 'python.exe'
            wgp = root / 'WanGP_Standalone' / 'wgp.py'
            models = root / 'models-existing'
            python.parent.mkdir(parents=True)
            wgp.parent.mkdir(parents=True)
            models.mkdir()
            python.write_bytes(b'python')
            wgp.write_text('# wgp', encoding='utf-8')
            template = root / 'animate.json'
            template.write_text('{"model_type":"animate","model_filename":"x.safetensors","settings_version":2.66}', encoding='utf-8')
            candidate = ExternalRuntimeCandidate(
                python_executable=str(python),
                wangp_script=str(wgp),
                working_directory=str(wgp.parent),
                settings_template=str(template),
                model_root=str(models),
                source='test',
            )
            video_path = root / 'local_wangp.json'
            image_path = root / 'local_wangp_image.json'
            state_path = root / 'runtime_install_state.json'
            preflight_path = root / 'runtime_preflight_config.json'
            fake_config = LocalWanGPConfig(
                python_executable=str(python), wangp_script=str(wgp), settings_template=str(template),
                working_directory=str(wgp.parent), strict_python_311=True, require_template=True,
            )
            with patch('app.runtime_adoption.validate_external_candidate', return_value=(SimpleNamespace(available=True), fake_config)), \
                 patch.object(LocalWanGPConfig, 'default_path', return_value=video_path), \
                 patch.object(LocalWanGPImageConfig, 'default_path', return_value=image_path), \
                 patch.object(RuntimeInstallState, 'default_path', return_value=state_path), \
                 patch.object(RuntimePreflightConfig, 'default_path', return_value=preflight_path):
                state = adopt_external_runtime(candidate)
                loaded = RuntimeInstallState.load(state_path)
            self.assertEqual(state.ownership, 'external')
            self.assertEqual(loaded.python_executable, str(python.resolve()))
            self.assertEqual(loaded.wangp_script, str(wgp.resolve()))
            self.assertEqual(loaded.model_root, str(models.resolve()))
            self.assertTrue(python.exists())
            self.assertTrue(wgp.exists())
            self.assertTrue(models.exists())

    def test_bridge_controller_does_not_rewrite_external_runtime_through_managed_installer(self):
        source = (Path(__file__).resolve().parents[1] / 'app' / 'runtime_bridge_controller.py').read_text(encoding='utf-8')
        self.assertIn("if state.ownership == 'external':", source)
        block = source.split("if state.ownership == 'external':", 1)[1].split('expected_python = (', 1)[0]
        self.assertNotIn('RuntimeInstaller(', block)


if __name__ == '__main__':
    unittest.main()
