from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.generation.errors import InvalidGenerationRequestError
from app.generation.image_provider import LocalWanGPImageConfig


class R5c6aImageMemoryHotfixTests(unittest.TestCase):
    def test_managed_memory_arguments_replace_legacy_duplicates(self):
        config = LocalWanGPImageConfig(
            python_executable='python.exe',
            wangp_script='wgp.py',
            settings_template='template.json',
            working_directory='C:/AI/WanGP',
            extra_arguments=[
                '--foo', 'bar',
                '--profile', '4',
                '--perc-reserved-mem-max', '0.50',
            ],
            memory_profile='5',
            reserved_memory_max=0.20,
        )
        self.assertEqual(
            config.to_video_config().extra_arguments,
            ['--foo', 'bar', '--profile', '5', '--perc-reserved-mem-max', '0.20'],
        )

    def test_auto_memory_controls_do_not_inject_cli_arguments(self):
        config = LocalWanGPImageConfig(
            extra_arguments=['--foo', 'bar'],
            memory_profile='',
            reserved_memory_max=0.0,
        )
        self.assertEqual(config.to_video_config().extra_arguments, ['--foo', 'bar'])

    def test_memory_controls_round_trip_in_local_image_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'local_wangp_image.json'
            config = LocalWanGPImageConfig(
                memory_profile='5',
                reserved_memory_max=0.20,
            )
            config.save(target)
            loaded = LocalWanGPImageConfig.load(target)
            self.assertEqual(loaded.memory_profile, '5')
            self.assertAlmostEqual(loaded.reserved_memory_max, 0.20)
            payload = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(payload['memory_profile'], '5')
            self.assertEqual(payload['reserved_memory_max'], 0.20)

    def test_invalid_profile_is_rejected_before_launch(self):
        config = LocalWanGPImageConfig(memory_profile='9')
        with self.assertRaises(InvalidGenerationRequestError):
            config.to_video_config()


if __name__ == '__main__':
    unittest.main()
