from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.generation.local_wangp import LocalWanGPConfig
from app.runtime_installer import RuntimeInstaller, resolve_wan_animate_settings_template
from app.runtime_preflight import RuntimePreflightConfig


class R5c3cAnimateTemplateContractTests(unittest.TestCase):
    def test_bundled_template_is_official_animate_settings(self):
        path = resolve_wan_animate_settings_template()
        self.assertIsNotNone(path)
        payload = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(payload['model_type'], 'animate')
        self.assertTrue(payload['model_filename'].endswith('wan2.2_animate_14B_quanto_bf16_int8.safetensors'))
        self.assertIn('settings_version', payload)
        self.assertIn('video_prompt_type', payload)

    def test_managed_bridge_replaces_stale_generic_settings_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_root = root / 'runtime'
            model_root = root / 'models'
            env_python = runtime_root / 'wangp_env' / 'python.exe'
            wgp = runtime_root / 'WanGP' / 'wgp.py'
            env_python.parent.mkdir(parents=True)
            wgp.parent.mkdir(parents=True)
            env_python.write_bytes(b'')
            wgp.write_bytes(b'')
            stale = root / 'wangp_settings.json'
            stale.write_text(json.dumps({'schema': 'generic'}), encoding='utf-8')
            config = LocalWanGPConfig(settings_template=str(stale))

            installer = RuntimeInstaller(RuntimePreflightConfig(str(runtime_root), str(model_root)))
            installer.runtime_root = runtime_root
            installer.model_root = model_root
            installer.env_root = runtime_root / 'wangp_env'
            installer.wangp_root = runtime_root / 'WanGP'

            with patch.object(LocalWanGPConfig, 'load', return_value=config), patch.object(config, 'save'):
                with patch('app.runtime_installer.LocalWanGPImageConfig.load') as image_load:
                    image_config = image_load.return_value
                    installer._write_bridge_config(env_python, _validated=True)

            template_path = Path(config.settings_template)
            payload = json.loads(template_path.read_text(encoding='utf-8'))
            self.assertEqual(payload['model_type'], 'animate')
            self.assertTrue(config.require_template)
            self.assertEqual(config.python_executable, str(env_python))
            self.assertEqual(config.wangp_script, str(wgp))
            image_config.save.assert_called_once()

    def test_runtime_asset_is_bundled_by_pyinstaller_spec(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / 'UnumSuntSpriteStudio.spec').read_text(encoding='utf-8')
        self.assertIn("runtime_datas = [('assets/runtime', 'assets/runtime')]", spec)


if __name__ == '__main__':
    unittest.main()
