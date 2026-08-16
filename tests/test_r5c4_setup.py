from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from app.runtime_adoption import ExternalRuntimeCandidate, auto_adopt_existing_runtime
from app.runtime_installer import RuntimeInstallState


class R5c4SetupTests(unittest.TestCase):
    def test_inno_script_defines_core_complete_custom_types(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = (root / 'installer' / 'UnumSuntSpriteStudio_R5c4a.iss').read_text(encoding='utf-8')
        self.assertIn('Name: "core"; Description: "Core', script)
        self.assertIn('Name: "complete"; Description: "Completa', script)
        self.assertIn('Name: "custom"; Description: "Personalizzata"; Flags: iscustom', script)
        self.assertIn('Name: "ai\\animate"', script)
        self.assertIn('--runtime-preflight', script)
        self.assertIn('--runtime-auto-adopt', script)
        self.assertIn('--runtime-install', script)
        self.assertIn('--skip-krea2', script)
        self.assertIn('--runtime-health', script)

    def test_setup_build_builds_standalone_before_inno(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = (root / 'build_setup_windows.ps1').read_text(encoding='utf-8')
        standalone = script.index('build_windows_standalone.ps1')
        compiler = script.index('ISCC.exe')
        self.assertLess(standalone, compiler)
        self.assertIn('JRSoftware.InnoSetup', script)
        self.assertIn('UnumSunt_Sprite_Studio_R5c4a_Setup_x64.exe', script)

    def test_auto_adopt_uses_first_healthy_candidate(self) -> None:
        first = ExternalRuntimeCandidate('a/python.exe', 'a/wgp.py', 'a', source='first')
        second = ExternalRuntimeCandidate('b/python.exe', 'b/wgp.py', 'b', source='second')
        unavailable = type('Report', (), {'available': False, 'summary': lambda self: 'not ready'})()
        available = type('Report', (), {'available': True, 'summary': lambda self: 'ready'})()
        adopted = RuntimeInstallState(status='ready', ownership='external', runtime_root='b')

        with patch('app.runtime_adoption.discover_existing_runtimes', return_value=[first, second]), \
             patch('app.runtime_adoption.validate_external_candidate', side_effect=[(unavailable, None), (available, None)]), \
             patch('app.runtime_adoption.adopt_external_runtime', return_value=adopted) as adopt:
            state, attempts = auto_adopt_existing_runtime()

        self.assertIs(state, adopted)
        self.assertEqual(attempts[0]['status'], 'not_ready')
        self.assertEqual(attempts[1]['status'], 'adopted')
        adopt.assert_called_once_with(second)

    def test_safe_cli_print_handles_windowed_stdout_none(self) -> None:
        import main
        with patch('main.sys.stdout', None):
            main._safe_cli_print('hidden progress')

    def test_main_exposes_setup_runtime_cli(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / 'main.py').read_text(encoding='utf-8')
        self.assertIn('"--runtime-discover"', text)
        self.assertIn('"--runtime-auto-adopt"', text)


if __name__ == '__main__':
    unittest.main()
