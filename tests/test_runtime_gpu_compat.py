from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from app.runtime_gpu_compat import (
    TorchRuntimeGpuProbe,
    architecture_supported,
    capability_to_architecture,
    parse_torch_gpu_probe,
    probe_torch_runtime_gpu,
)


class RuntimeGpuCompatibilityTests(unittest.TestCase):
    def test_capability_to_architecture(self):
        self.assertEqual(capability_to_architecture((6, 1)), 'sm_61')
        self.assertEqual(capability_to_architecture('8.6'), 'sm_86')

    def test_sm61_is_rejected_by_runtime_arch_list_from_gtx1050_log(self):
        supported = ('sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120')
        self.assertFalse(architecture_supported('6.1', supported))
        self.assertTrue(architecture_supported('8.6', supported))
        self.assertTrue(architecture_supported('12.0', supported))

    def test_compute_ptx_entry_is_accepted(self):
        self.assertTrue(architecture_supported('12.0', ('compute_120',)))

    def test_parse_probe_marks_default_device_incompatible(self):
        probe = parse_torch_gpu_probe({
            'python_version': '3.11.14',
            'torch_version': '2.10.0+cu130',
            'torch_cuda_version': '13.0',
            'cuda_available': True,
            'arch_list': ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120'],
            'devices': [{'index': 0, 'name': 'NVIDIA GeForce GTX 1050', 'capability': [6, 1]}],
        })
        self.assertTrue(probe.available)
        self.assertFalse(probe.default_device_compatible)
        self.assertIn('sm_61', probe.detail())
        self.assertIn('NON compatibile', probe.detail())

    def test_parse_probe_accepts_rtx3070_sm86(self):
        probe = parse_torch_gpu_probe({
            'python_version': '3.11.14',
            'torch_version': '2.10.0+cu130',
            'torch_cuda_version': '13.0',
            'cuda_available': True,
            'arch_list': ['sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120'],
            'devices': [{'index': 0, 'name': 'NVIDIA GeForce RTX 3070', 'capability': [8, 6]}],
        })
        self.assertTrue(probe.default_device_compatible)
        self.assertIn('sm_86', probe.detail())

    def test_probe_reads_json_from_managed_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            python = Path(tmp) / 'python.exe'
            python.write_bytes(b'')
            payload = {
                'python_version': '3.11.14', 'torch_version': '2.10.0', 'torch_cuda_version': '13.0',
                'cuda_available': True, 'arch_list': ['sm_86'],
                'devices': [{'index': 0, 'name': 'RTX 3070', 'capability': [8, 6]}],
            }
            def runner(*_args, **_kwargs):
                return subprocess.CompletedProcess([], 0, json.dumps(payload) + '\n', '')
            probe = probe_torch_runtime_gpu(python, runner=runner)
        self.assertTrue(probe.default_device_compatible)


if __name__ == '__main__':
    unittest.main()
