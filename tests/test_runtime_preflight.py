from __future__ import annotations

from collections import namedtuple
from pathlib import Path
import tempfile
import unittest

from app.runtime_gpu_compat import TorchRuntimeGpuProbe, TorchGpuDevice

from app.runtime_preflight import (
    GIB,
    STATUS_BLOCKED,
    STATUS_INFO,
    STATUS_READY,
    NvidiaGpuInfo,
    NvidiaProbe,
    PreflightCheck,
    RuntimePreflightConfig,
    cuda_version_compatible,
    load_install_plan,
    parse_gpu_csv,
    parse_nvidia_smi_summary,
    path_drive_key,
    run_runtime_preflight,
    storage_requirements_by_destination,
    validate_windows_path_text,
)

Usage = namedtuple('Usage', 'total used free')


def existing_info() -> PreflightCheck:
    return PreflightCheck('runtime.existing', 'Runtime esistente', STATUS_INFO, 'none', blocking=False)


def writable_ok(path: Path):
    return True, f'writable:{path}'


class RuntimePreflightTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_install_plan()
        self.good_gpu = NvidiaProbe(
            True,
            '13.1',
            (NvidiaGpuInfo('NVIDIA GeForce RTX 3070', '591.00', 8192),),
            '',
        )

    def _run(self, *, gpu=None, free_gib=500.0, memory_gib=16.0, runtime=r'C:\AI\runtime', models=r'C:\AI\models', torch_probe=None):
        return run_runtime_preflight(
            RuntimePreflightConfig(runtime_root=runtime, model_root=models),
            plan=self.plan,
            platform_name='nt',
            is_64bit=True,
            nvidia_probe=gpu or self.good_gpu,
            writable_probe=writable_ok,
            disk_usage=lambda _path: Usage(1000 * GIB, 0, int(free_gib * GIB)),
            memory_bytes=int(memory_gib * GIB),
            existing_runtime_check=existing_info,
            torch_runtime_probe=torch_probe,
        )

    def test_parse_nvidia_smi_summary(self):
        driver, cuda = parse_nvidia_smi_summary('| NVIDIA-SMI 591.00 Driver Version: 591.00 CUDA Version: 13.1 |')
        self.assertEqual(driver, '591.00')
        self.assertEqual(cuda, '13.1')

    def test_parse_gpu_csv(self):
        gpus = parse_gpu_csv('NVIDIA GeForce RTX 3070, 591.00, 8192\nRTX 5070, 591.00, 8192')
        self.assertEqual(len(gpus), 2)
        self.assertEqual(gpus[0].memory_mib, 8192)

    def test_cuda_version_comparison(self):
        self.assertTrue(cuda_version_compatible('13.1', '13.0'))
        self.assertTrue(cuda_version_compatible('13.0', '13.0'))
        self.assertFalse(cuda_version_compatible('12.8', '13.0'))

    def test_install_plan_has_cuda13_and_krea_checkpoint_size(self):
        self.assertEqual(self.plan.minimum_reported_cuda, '13.0')
        krea = next(c for c in self.plan.components if c.id == 'krea2_turbo')
        self.assertEqual(krea.installed_gib, 13.5)
        self.assertTrue(krea.estimate)

    def test_rtx3070_16gb_ram_is_not_blocked_by_model_or_ram(self):
        report = self._run(memory_gib=16.0)
        self.assertEqual(report.status, STATUS_READY)
        ram = next(c for c in report.checks if c.id == 'system.ram')
        policy = next(c for c in report.checks if c.id == 'system.gpu_policy')
        self.assertEqual(ram.status, STATUS_INFO)
        self.assertEqual(policy.status, STATUS_INFO)
        self.assertFalse(ram.blocking)
        self.assertFalse(policy.blocking)

    def test_installed_runtime_reports_gtx1050_sm61_as_warning_not_arbitrary_hardware_block(self):
        probe = TorchRuntimeGpuProbe(
            True, '3.11.14', '2.10.0+cu130', '13.0', True,
            ('sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120'),
            (TorchGpuDevice(0, 'NVIDIA GeForce GTX 1050', '6.1', 'sm_61', False),),
        )
        report = self._run(torch_probe=probe)
        guard = next(c for c in report.checks if c.id == 'torch.gpu_compatibility')
        self.assertEqual(guard.status, 'WARNING')
        self.assertFalse(guard.blocking)
        self.assertIn('sm_61', guard.detail)

    def test_installed_runtime_reports_rtx3070_sm86_ready(self):
        probe = TorchRuntimeGpuProbe(
            True, '3.11.14', '2.10.0+cu130', '13.0', True,
            ('sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120'),
            (TorchGpuDevice(0, 'NVIDIA GeForce RTX 3070', '8.6', 'sm_86', True),),
        )
        report = self._run(torch_probe=probe)
        guard = next(c for c in report.checks if c.id == 'torch.gpu_compatibility')
        self.assertEqual(guard.status, STATUS_READY)
        self.assertFalse(guard.blocking)

    def test_missing_cuda_blocks(self):
        report = self._run(gpu=NvidiaProbe(False, None, (), 'nvidia-smi missing'))
        self.assertEqual(report.status, STATUS_BLOCKED)
        cuda = next(c for c in report.checks if c.id == 'cuda.nvidia_smi')
        self.assertTrue(cuda.blocking)

    def test_old_cuda_driver_blocks(self):
        report = self._run(gpu=NvidiaProbe(True, '12.8', (NvidiaGpuInfo('Any NVIDIA GPU', '570', 2048),), ''))
        self.assertEqual(report.status, STATUS_BLOCKED)
        cuda = next(c for c in report.checks if c.id == 'cuda.compatibility')
        self.assertIn('required >= 13.0', cuda.detail)

    def test_insufficient_storage_blocks(self):
        report = self._run(free_gib=10)
        self.assertEqual(report.status, STATUS_BLOCKED)
        storage = [c for c in report.checks if c.id.startswith('storage.')]
        self.assertTrue(storage)
        self.assertTrue(any(c.blocking for c in storage))

    def test_same_drive_aggregates_runtime_and_models(self):
        report = self._run(runtime=r'C:\AI\runtime', models=r'C:\AI\models')
        self.assertEqual(len(report.storage_targets), 1)
        self.assertIn('runtime', report.storage_targets[0].destination)
        self.assertIn('models', report.storage_targets[0].destination)

    def test_different_drives_are_checked_separately(self):
        report = self._run(runtime=r'C:\AI\runtime', models=r'D:\AI\models')
        self.assertEqual(len(report.storage_targets), 2)
        self.assertEqual({t.drive_key for t in report.storage_targets}, {'c:\\', 'd:\\'})

    def test_windows_path_validation(self):
        ok, errors = validate_windows_path_text(r'C:\AI\WanGP')
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        ok, errors = validate_windows_path_text(r'C:\AI\CON\models')
        self.assertFalse(ok)
        self.assertTrue(any('reserved' in e.lower() for e in errors))

    def test_drive_key_uses_windows_anchor_even_off_windows(self):
        self.assertEqual(path_drive_key(Path(r'G:\AI\runtime'), platform_name='nt'), 'g:\\')

    def test_storage_plan_reserves_both_destinations(self):
        req = storage_requirements_by_destination(self.plan)
        self.assertGreater(req['runtime'], 0)
        self.assertGreater(req['models'], req['runtime'])

    def test_report_contains_provisional_size_note(self):
        report = self._run()
        self.assertTrue(any('Provisional space estimates' in note for note in report.notes))

    def test_cli_and_spec_are_wired_for_preflight(self):
        root = Path(__file__).resolve().parents[1]
        main_text = (root / 'main.py').read_text(encoding='utf-8')
        spec_text = (root / 'UnumSuntSpriteStudio.spec').read_text(encoding='utf-8')
        self.assertIn('--runtime-preflight', main_text)
        self.assertIn("runtime_datas = [('assets/runtime', 'assets/runtime')]", spec_text)


if __name__ == '__main__':
    unittest.main()
