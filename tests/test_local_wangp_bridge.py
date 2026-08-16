from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import sys
import unittest

import numpy as np
from PIL import Image

from app.generation.base import GenerationJobContext
from app.generation.local_wangp import (
    LocalWanGPConfig,
    LocalWanGPProvider,
    WanGPJobAdapter,
    WanGPProgressParser,
)
from app.generation.models import GenerationProgress, GenerationRequest


class LocalWanGPBridgeTests(unittest.TestCase):
    @staticmethod
    def fixture_script() -> Path:
        return Path(__file__).resolve().parents[1] / 'tools' / 'mock_wangp_cli.py'

    def make_config(self, root: Path, *, require_template: bool = False) -> LocalWanGPConfig:
        return LocalWanGPConfig(
            python_executable=sys.executable,
            wangp_script=str(self.fixture_script()),
            settings_template='',
            working_directory=str(self.fixture_script().parent),
            strict_python_311=False,
            require_template=require_template,
        )

    def make_reference(self, root: Path) -> Path:
        rgba = np.zeros((32, 32, 4), dtype=np.uint8)
        rgba[8:28, 10:22, :3] = (140, 80, 50)
        rgba[8:28, 10:22, 3] = 255
        path = root / 'reference.png'
        Image.fromarray(rgba, mode='RGBA').save(path)
        return path

    def make_context(self, root: Path, progress: list[GenerationProgress], cancel_event: Event | None = None) -> GenerationJobContext:
        for name in ('input', 'output', 'logs'):
            (root / name).mkdir(exist_ok=True)
        return GenerationJobContext(
            job_directory=root,
            input_directory=root / 'input',
            output_directory=root / 'output',
            logs_directory=root / 'logs',
            cancel_event=cancel_event or Event(),
            progress_callback=progress.append,
        )

    def test_progress_parser_reads_wangp_step(self) -> None:
        progress = WanGPProgressParser().parse('[12/30] Prompt 1/3 - Denoising')
        self.assertIsNotNone(progress)
        self.assertEqual(progress.state, 'denoising')  # type: ignore[union-attr]
        self.assertEqual(progress.current_step, 12)  # type: ignore[union-attr]
        self.assertEqual(progress.total_steps, 30)  # type: ignore[union-attr]
        self.assertGreater(progress.fraction, 0.27)  # type: ignore[union-attr]

    def test_template_adapter_preserves_numeric_placeholders(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / 'template.json'
            template.write_text(
                json.dumps({'seed': '${SEED}', 'width': '${WIDTH}', 'path': '${REFERENCE_IMAGE}', 'prompt': 'Do: ${POSITIVE_PROMPT}'}),
                encoding='utf-8',
            )
            config = self.make_config(root)
            config.settings_template = str(template)
            payload = WanGPJobAdapter().build_payload(
                GenerationRequest(job_id='adapter', seed=42, width=320, positive_prompt='walk'),
                config,
                {'reference_image': 'C:/sprite.png', 'motion_video': None, 'output_directory': 'C:/out'},
            )
            self.assertEqual(payload['seed'], 42)
            self.assertEqual(payload['width'], 320)
            self.assertEqual(payload['path'], 'C:/sprite.png')
            self.assertEqual(payload['prompt'], 'Do: walk')

    def test_template_adapter_exposes_background_contract_placeholders(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / 'background_template.json'
            template.write_text(
                json.dumps({
                    'hex': '${BACKGROUND_HEX}',
                    'rgb': '${BACKGROUND_RGB_LIST}',
                    'r': '${BACKGROUND_R}',
                    'text': 'flat ${BACKGROUND_HEX} background',
                }),
                encoding='utf-8',
            )
            config = self.make_config(root)
            config.settings_template = str(template)
            payload = WanGPJobAdapter().build_payload(
                GenerationRequest(
                    job_id='background_adapter',
                    metadata={'requested_background_rgb': [12, 34, 56]},
                ),
                config,
                {'reference_image': None, 'motion_video': None, 'output_directory': 'C:/out'},
            )
            self.assertEqual(payload['hex'], '#0C2238')
            self.assertEqual(payload['rgb'], [12, 34, 56])
            self.assertEqual(payload['r'], 12)
            self.assertEqual(payload['text'], 'flat #0C2238 background')

    def test_health_check_accepts_development_runtime(self) -> None:
        with TemporaryDirectory() as temp_dir:
            provider = LocalWanGPProvider(self.make_config(Path(temp_dir)))
            report = provider.health_check()
            self.assertTrue(report.available, report.summary())
            self.assertIsNotNone(report.python_version)

    def test_dry_run_uses_external_process_and_logs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = self.make_reference(root)
            progress: list[GenerationProgress] = []
            provider = LocalWanGPProvider(self.make_config(root))
            result = provider.run(
                GenerationRequest(
                    job_id='dry_run',
                    provider='local_wangp',
                    model='fixture',
                    reference_image=str(reference),
                    metadata={'dry_run': True},
                ),
                self.make_context(root, progress),
            )
            self.assertEqual(result.state, 'completed')
            self.assertIsNone(result.video_path)
            self.assertTrue(result.metadata['dry_run'])
            self.assertTrue((root / 'wangp_settings.json').exists())
            self.assertTrue((root / 'logs' / 'stdout.log').exists())

    def test_external_fixture_generates_importable_video(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = self.make_reference(root)
            progress: list[GenerationProgress] = []
            provider = LocalWanGPProvider(self.make_config(root))
            result = provider.run(
                GenerationRequest(
                    job_id='generate',
                    provider='local_wangp',
                    model='fixture',
                    reference_image=str(reference),
                    width=128,
                    height=96,
                    frames=8,
                    fps=12.0,
                    steps=4,
                ),
                self.make_context(root, progress),
            )
            self.assertTrue(result.is_completed)
            self.assertTrue(Path(result.video_path).exists())  # type: ignore[arg-type]
            self.assertEqual(result.metadata['width'], 128)
            self.assertEqual(result.metadata['height'], 96)
            self.assertEqual(result.metadata['frames'], 8)
            self.assertTrue(any(item.state == 'denoising' for item in progress))
            self.assertTrue((root / 'generation_manifest.json').exists())

    def test_contract_metadata_records_planned_and_actual_output(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = self.make_reference(root)
            provider = LocalWanGPProvider(self.make_config(root))
            contract = {
                'resolution': {
                    'resolution_class': '360p',
                    'aspect_ratio': '4:3',
                    'width': 128,
                    'height': 96,
                    'value': '128x96',
                    'label': 'fixture',
                    'source': 'test',
                },
                'frames': {'requested': 12, 'effective': 9, 'rule': '4n+1_floor'},
                'fps': {
                    'requested_fps': 12.0,
                    'effective_fps': 12.0,
                    'source': 'request',
                    'force_fps': '',
                },
                'steps': 4,
            }
            result = provider.run(
                GenerationRequest(
                    job_id='contract_output',
                    provider='local_wangp',
                    model='fixture',
                    reference_image=str(reference),
                    width=128,
                    height=96,
                    frames=9,
                    fps=12.0,
                    steps=4,
                    metadata={
                        'wan_contract': contract,
                        'requested_resolution_class': '360p',
                        'requested_aspect_ratio': '4:3',
                        'requested_frames': 12,
                        'effective_frames': 9,
                        'requested_fps': 12.0,
                        'effective_fps': 12.0,
                        'fps_source': 'request',
                    },
                ),
                self.make_context(root, []),
            )
            self.assertEqual(result.metadata['requested_frames'], 12)
            self.assertEqual(result.metadata['effective_frames'], 9)
            self.assertEqual(result.metadata['actual_frames'], 9)
            self.assertTrue(result.metadata['resolution_match'])
            self.assertTrue(result.metadata['frames_match'])
            self.assertTrue(result.metadata['fps_match'])
            manifest = json.loads((root / 'generation_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['schema'], 'unum-sunt-generation-manifest-v3')
            self.assertEqual(manifest['metadata']['execution_contract']['actual']['frames'], 9)

    def test_pre_cancelled_context_does_not_start_process(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = self.make_reference(root)
            cancel_event = Event(); cancel_event.set()
            provider = LocalWanGPProvider(self.make_config(root))
            from app.generation.errors import GenerationCancelledError
            with self.assertRaises(GenerationCancelledError):
                provider.run(
                    GenerationRequest(
                        job_id='cancelled',
                        provider='local_wangp',
                        reference_image=str(reference),
                    ),
                    self.make_context(root, [], cancel_event),
                )

    def test_job_manager_runs_local_bridge_asynchronously(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = self.make_reference(root)
            from app.generation.manager import GenerationJobManager
            from app.generation.registry import ProviderRegistry
            provider = LocalWanGPProvider(self.make_config(root))
            manager = GenerationJobManager(
                ProviderRegistry([provider]),
                workspace_root=root / 'jobs',
            )
            job_id = manager.submit(
                GenerationRequest(
                    job_id='async_local',
                    provider='local_wangp',
                    model='fixture',
                    reference_image=str(reference),
                    width=96,
                    height=96,
                    frames=6,
                    fps=12.0,
                )
            )
            import time
            deadline = time.time() + 15
            snapshot = manager.get_snapshot(job_id)
            while snapshot and snapshot.state not in {'completed', 'failed', 'cancelled'} and time.time() < deadline:
                time.sleep(0.05)
                snapshot = manager.get_snapshot(job_id)
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot.state, 'completed')  # type: ignore[union-attr]
            self.assertTrue(snapshot.result and snapshot.result.is_completed)  # type: ignore[union-attr]
            job_dir = Path(snapshot.job_directory)  # type: ignore[union-attr]
            self.assertTrue((job_dir / 'request.json').exists())
            self.assertTrue((job_dir / 'wangp_settings.json').exists())
            self.assertTrue((job_dir / 'logs' / 'stdout.log').exists())
            manager.shutdown()



    def test_official_settings_template_binds_request_and_media(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / 'animate.json'
            template.write_text(
                json.dumps({
                    'settings_version': 2.66,
                    'model_type': 'animate',
                    'video_prompt_type': 'PVBKI',
                    'image_prompt_type': '',
                    'prompt': 'old prompt',
                    'negative_prompt': '',
                    'resolution': '832x480',
                    'video_length': 81,
                    'seed': -1,
                    'num_inference_steps': 30,
                    'force_fps': 'control',
                }),
                encoding='utf-8',
            )
            config = self.make_config(root)
            config.settings_template = str(template)
            request = GenerationRequest(
                job_id='official_binding',
                reference_image='C:/job/reference.png',
                motion_video='C:/job/control.mp4',
                positive_prompt='walk on magenta',
                negative_prompt='camera movement',
                seed=18274,
                width=320,
                height=320,
                frames=24,
                fps=12.0,
                steps=10,
            )
            paths = {
                'reference_image': 'C:/copied/reference.png',
                'motion_video': 'C:/copied/control.mp4',
                'output_directory': 'C:/out',
            }
            adapter = WanGPJobAdapter()
            payload = adapter.build_payload(request, config, paths)
            self.assertEqual(payload['prompt'], 'walk on magenta')
            self.assertEqual(payload['negative_prompt'], 'camera movement')
            self.assertEqual(payload['resolution'], '320x320')
            self.assertEqual(payload['video_length'], 24)
            self.assertEqual(payload['seed'], 18274)
            self.assertEqual(payload['num_inference_steps'], 10)
            self.assertEqual(payload['image_refs'], ['C:/copied/reference.png'])
            self.assertNotIn('image_start', payload)
            self.assertEqual(payload['video_guide'], 'C:/copied/control.mp4')
            self.assertEqual(payload['force_fps'], 'control')
            report = adapter.binding_report(payload, request, paths)
            self.assertEqual(report['adapter_mode'], 'official_settings_direct')
            self.assertIn('image_refs', report['bound_fields'])
            self.assertIn('video_guide', report['bound_fields'])



    def test_official_start_image_preset_binds_image_start(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / 'i2v.json'
            template.write_text(
                json.dumps({
                    'settings_version': 2.66,
                    'model_type': 'i2v',
                    'image_prompt_type': 'S',
                    'video_prompt_type': '',
                    'prompt': 'old',
                    'negative_prompt': '',
                    'resolution': '832x480',
                    'video_length': 81,
                    'seed': -1,
                    'num_inference_steps': 30,
                }),
                encoding='utf-8',
            )
            config = self.make_config(root)
            config.settings_template = str(template)
            request = GenerationRequest(
                job_id='start_image_binding',
                reference_image='C:/job/start.png',
                positive_prompt='idle',
                width=320,
                height=320,
                frames=24,
                seed=7,
                steps=10,
            )
            paths = {
                'reference_image': 'C:/copied/start.png',
                'motion_video': None,
                'output_directory': 'C:/out',
            }
            payload = WanGPJobAdapter().build_payload(request, config, paths)
            self.assertEqual(payload['image_start'], ['C:/copied/start.png'])
            self.assertNotIn('image_refs', payload)

    def test_official_combined_preset_binds_both_image_slots(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / 'combined.json'
            template.write_text(
                json.dumps({
                    'settings_version': 2.66,
                    'model_type': 'custom',
                    'image_prompt_type': 'S',
                    'video_prompt_type': 'IV',
                    'prompt': '',
                    'negative_prompt': '',
                    'resolution': '832x480',
                    'video_length': 81,
                    'seed': -1,
                    'num_inference_steps': 30,
                }),
                encoding='utf-8',
            )
            config = self.make_config(root)
            config.settings_template = str(template)
            request = GenerationRequest(
                job_id='combined_binding',
                reference_image='C:/job/ref.png',
                motion_video='C:/job/control.mp4',
                width=320,
                height=320,
                frames=24,
                seed=7,
                steps=10,
            )
            paths = {
                'reference_image': 'C:/copied/ref.png',
                'motion_video': 'C:/copied/control.mp4',
                'output_directory': 'C:/out',
            }
            payload = WanGPJobAdapter().build_payload(request, config, paths)
            self.assertEqual(payload['image_refs'], ['C:/copied/ref.png'])
            self.assertEqual(payload['image_start'], ['C:/copied/ref.png'])
            self.assertEqual(payload['video_guide'], 'C:/copied/control.mp4')

    def test_standard_wangp_layout_falls_back_to_script_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / 'WanGP'
            work = root / 'WORK'
            (repo / 'models').mkdir(parents=True)
            work.mkdir()
            (repo / 'wgp.py').write_text('print("fixture")\n', encoding='utf-8')
            (repo / 'models' / '_settings.json').write_text('{}', encoding='utf-8')
            config = LocalWanGPConfig(
                python_executable=sys.executable,
                wangp_script=str(repo / 'wgp.py'),
                settings_template='',
                working_directory=str(work),
                strict_python_311=False,
                require_template=False,
            )
            provider = LocalWanGPProvider(config)
            resolved, warning = provider.resolve_working_directory()
            self.assertEqual(resolved, repo)
            self.assertIsNotNone(warning)
            report = provider.health_check()
            self.assertTrue(report.available, report.summary())
            self.assertTrue(any('corretta automaticamente' in item for item in report.warnings))

    def test_standard_wangp_layout_requires_settings_marker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / 'WanGP'
            repo.mkdir()
            (repo / 'wgp.py').write_text('print("fixture")\n', encoding='utf-8')
            config = LocalWanGPConfig(
                python_executable=sys.executable,
                wangp_script=str(repo / 'wgp.py'),
                settings_template='',
                working_directory=str(repo),
                strict_python_311=False,
                require_template=False,
            )
            report = LocalWanGPProvider(config).health_check()
            self.assertFalse(report.available)
            marker_check = next(item for item in report.checks if item.name == 'WanGP models/_settings.json')
            self.assertFalse(marker_check.ok)

    def test_dry_run_executes_standard_wangp_from_resolved_root(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / 'WanGP'
            work = root / 'WORK'
            (repo / 'models').mkdir(parents=True)
            work.mkdir()
            (repo / 'models' / '_settings.json').write_text('{"ready": true}', encoding='utf-8')
            (repo / 'wgp.py').write_text(
                "from pathlib import Path\n"
                "import argparse\n"
                "p=argparse.ArgumentParser()\n"
                "p.add_argument('--process')\n"
                "p.add_argument('--output-dir')\n"
                "p.add_argument('--verbose')\n"
                "p.add_argument('--dry-run', action='store_true')\n"
                "p.parse_args()\n"
                "Path('models/_settings.json').read_text(encoding='utf-8')\n"
                "print('dry-run ok')\n",
                encoding='utf-8',
            )
            config = LocalWanGPConfig(
                python_executable=sys.executable,
                wangp_script=str(repo / 'wgp.py'),
                settings_template='',
                working_directory=str(work),
                strict_python_311=False,
                require_template=False,
            )
            reference = self.make_reference(root)
            progress: list[GenerationProgress] = []
            provider = LocalWanGPProvider(config)
            result = provider.run(
                GenerationRequest(
                    job_id='resolved_root',
                    provider='local_wangp',
                    model='fixture',
                    reference_image=str(reference),
                    metadata={'dry_run': True},
                ),
                self.make_context(root, progress),
            )
            self.assertEqual(result.state, 'completed')
            self.assertTrue(result.metadata['dry_run'])
            provider_payload = json.loads((root / 'provider_settings.json').read_text(encoding='utf-8'))
            self.assertEqual(Path(provider_payload['resolved_working_directory']), repo)
            self.assertIn('corretta automaticamente', provider_payload['working_directory_warning'])



if __name__ == '__main__':
    unittest.main()
