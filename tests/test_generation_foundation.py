from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest

from app.generation.base import GenerationJobContext
from app.generation.manager import GenerationJobManager
from app.generation.mock_provider import MockVideoProvider
from app.generation.models import GenerationProgress, GenerationRequest
from app.generation.registry import ProviderRegistry


class GenerationFoundationTests(unittest.TestCase):
    def test_provider_registry_and_capabilities(self) -> None:
        provider = MockVideoProvider()
        registry = ProviderRegistry([provider])
        self.assertIs(registry.get('mock_video'), provider)
        self.assertTrue(provider.get_capabilities().image_to_video)
        self.assertTrue(provider.get_capabilities().cancellation)

    def test_mock_provider_creates_video_and_manifest(self) -> None:
        provider = MockVideoProvider()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ('input', 'output', 'logs'):
                (root / name).mkdir()
            progress: list[GenerationProgress] = []
            context = GenerationJobContext(
                job_directory=root,
                input_directory=root / 'input',
                output_directory=root / 'output',
                logs_directory=root / 'logs',
                cancel_event=Event(),
                progress_callback=progress.append,
            )
            result = provider.run(
                GenerationRequest(
                    job_id='mock_test',
                    frames=8,
                    width=128,
                    height=128,
                    fps=12.0,
                ),
                context,
            )
            self.assertTrue(result.is_completed)
            self.assertTrue(Path(result.video_path).exists())  # type: ignore[arg-type]
            self.assertGreater(Path(result.video_path).stat().st_size, 0)  # type: ignore[arg-type]
            self.assertTrue((root / 'generation_manifest.json').exists())
            self.assertGreater(len(progress), 5)
            from app.video_source import VideoSource
            source = VideoSource()
            metadata = source.open(result.video_path)  # type: ignore[arg-type]
            self.assertEqual(metadata.frame_count, 8)
            self.assertEqual(metadata.width, 128)
            self.assertEqual(metadata.height, 128)
            source.close()

    def test_mock_provider_uses_requested_background_color(self) -> None:
        provider = MockVideoProvider()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ('input', 'output', 'logs'):
                (root / name).mkdir()
            context = GenerationJobContext(
                job_directory=root,
                input_directory=root / 'input',
                output_directory=root / 'output',
                logs_directory=root / 'logs',
                cancel_event=Event(),
                progress_callback=lambda progress: None,
            )
            result = provider.run(
                GenerationRequest(
                    job_id='mock_bg',
                    frames=4,
                    width=96,
                    height=96,
                    fps=12.0,
                    metadata={'requested_background_rgb': [15, 25, 35], 'background_mode': 'solid_chroma'},
                ),
                context,
            )
            from app.video_source import VideoSource
            source = VideoSource()
            source.open(result.video_path)  # type: ignore[arg-type]
            frame = source.get_frame_rgb(0)
            source.close()
            corner = frame[:8, :8].reshape(-1, 3).mean(axis=0)
            self.assertLess(abs(float(corner[0]) - 15), 8)
            self.assertLess(abs(float(corner[1]) - 25), 8)
            self.assertLess(abs(float(corner[2]) - 35), 8)
            self.assertEqual(result.metadata['requested_background_rgb'], [15, 25, 35])

    def test_job_manager_writes_normalized_job_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            manager = GenerationJobManager(
                ProviderRegistry([MockVideoProvider()]),
                workspace_root=temp_dir,
            )
            job_id = manager.submit(
                GenerationRequest(
                    job_id='manager_test',
                    frames=6,
                    width=96,
                    height=96,
                    fps=12.0,
                )
            )
            import time
            deadline = time.time() + 10
            snapshot = manager.get_snapshot(job_id)
            while snapshot and snapshot.state not in {'completed', 'failed', 'cancelled'} and time.time() < deadline:
                time.sleep(0.05)
                snapshot = manager.get_snapshot(job_id)
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot.state, 'completed')  # type: ignore[union-attr]
            job_dir = Path(snapshot.job_directory)  # type: ignore[union-attr]
            self.assertTrue((job_dir / 'request.json').exists())
            self.assertTrue((job_dir / 'status.json').exists())
            self.assertTrue((job_dir / 'manifest.json').exists())
            data = json.loads((job_dir / 'status.json').read_text(encoding='utf-8'))
            self.assertEqual(data['state'], 'completed')
            manager.shutdown()

    def test_mock_provider_honors_pre_cancelled_context(self) -> None:
        provider = MockVideoProvider()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ('input', 'output', 'logs'):
                (root / name).mkdir()
            cancel_event = Event()
            cancel_event.set()
            context = GenerationJobContext(
                job_directory=root,
                input_directory=root / 'input',
                output_directory=root / 'output',
                logs_directory=root / 'logs',
                cancel_event=cancel_event,
                progress_callback=lambda progress: None,
            )
            from app.generation.errors import GenerationCancelledError
            with self.assertRaises(GenerationCancelledError):
                provider.run(
                    GenerationRequest(
                        job_id='cancel_test',
                        frames=8,
                        width=96,
                        height=96,
                        fps=12.0,
                    ),
                    context,
                )


if __name__ == '__main__':
    unittest.main()
