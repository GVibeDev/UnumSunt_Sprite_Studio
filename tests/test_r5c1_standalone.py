from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from app.runtime_paths import local_data_root, roaming_config_root
from app.standalone_selfcheck import build_self_check_payload
from app.version import APP_VERSION


class R5c1StandaloneTests(unittest.TestCase):
    def test_windows_roaming_path_remains_backward_compatible(self) -> None:
        path = roaming_config_root(
            platform_name='nt',
            env={'APPDATA': r'C:\Users\Tester\AppData\Roaming'},
            home=r'C:\Users\Tester',
        )
        normalized = str(path).replace('\\', '/')
        self.assertEqual(normalized, 'C:/Users/Tester/AppData/Roaming/UnumSuntSpriteStudio')

    def test_windows_local_path_remains_backward_compatible(self) -> None:
        path = local_data_root(
            platform_name='nt',
            env={'LOCALAPPDATA': r'C:\Users\Tester\AppData\Local'},
            home=r'C:\Users\Tester',
        )
        normalized = str(path).replace('\\', '/')
        self.assertEqual(normalized, 'C:/Users/Tester/AppData/Local/UnumSuntSpriteStudio')

    def test_self_check_payload_can_validate_paths_without_gui_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch('app.standalone_selfcheck.ensure_user_directories', return_value={
                'config': root / 'config',
                'local_data': root / 'local',
                'logs': root / 'local' / 'logs',
                'cache': root / 'local' / 'cache',
                'generation_jobs': root / 'local' / 'generation_jobs',
            }):
                for path in (root / 'config', root / 'local', root / 'local' / 'logs', root / 'local' / 'cache', root / 'local' / 'generation_jobs'):
                    path.mkdir(parents=True, exist_ok=True)
                payload = build_self_check_payload(import_runtime=False)
        self.assertEqual(payload['status'], 'passed')
        self.assertEqual(payload['version'], APP_VERSION)
        self.assertFalse(payload['ai_runtime']['bundled'])

    def test_version_is_current_release(self) -> None:
        self.assertEqual(APP_VERSION, 'R5c7')


if __name__ == '__main__':
    unittest.main()
