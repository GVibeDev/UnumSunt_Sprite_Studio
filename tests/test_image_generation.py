from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from PIL import Image

from app.generation.image_provider import (
    LocalWanGPImageConfig,
    LocalWanGPImageProvider,
    MockImageProvider,
    WanGPImageSettingsAdapter,
)
from app.generation.manager import GenerationJobManager
from app.generation.models import GenerationRequest
from app.generation.registry import ProviderRegistry
from app.project_store import ProjectStore


class ImageGenerationTests(unittest.TestCase):
    def _request(self, *, task: str = 'text_to_image', reference: str | None = None) -> GenerationRequest:
        return GenerationRequest(
            job_id='img_test',
            provider='mock_image',
            model='mock_image_v1',
            task=task,
            reference_image=reference,
            positive_prompt='full body character on clean background',
            negative_prompt='text, watermark',
            seed=1234,
            width=128,
            height=96,
            frames=1,
            fps=1.0,
            steps=8,
        )

    def test_mock_image_capabilities(self) -> None:
        caps = MockImageProvider().get_capabilities()
        self.assertTrue(caps.text_to_image)
        self.assertTrue(caps.image_to_image)
        self.assertFalse(caps.image_to_video)

    def test_mock_text_to_image_writes_png_and_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            manager = GenerationJobManager(ProviderRegistry([MockImageProvider()]), workspace_root=Path(temp_dir))
            job_id = manager.submit(self._request())
            runtime = manager._jobs[job_id]
            runtime.future.result(timeout=10)  # type: ignore[union-attr]
            snapshot = manager.get_snapshot(job_id)
            self.assertIsNotNone(snapshot)
            result = snapshot.result  # type: ignore[union-attr]
            self.assertTrue(result.is_completed)  # type: ignore[union-attr]
            self.assertIsNone(result.video_path)  # type: ignore[union-attr]
            image_path = Path(result.image_path)  # type: ignore[arg-type,union-attr]
            self.assertTrue(image_path.is_file())
            with Image.open(image_path) as image:
                self.assertEqual(image.size, (128, 96))
            manifest = Path(snapshot.job_directory) / 'image_generation_manifest.json'  # type: ignore[union-attr]
            payload = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(payload['schema'], 'unum-sunt-image-generation-manifest-v1')
            self.assertEqual(payload['task'], 'text_to_image')
            manager.shutdown()

    def test_mock_image_to_image_requires_reference(self) -> None:
        provider = MockImageProvider()
        with self.assertRaises(Exception):
            provider.validate_request(self._request(task='image_to_image'))

    def test_mock_image_to_image_accepts_reference(self) -> None:
        with TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / 'master.png'
            Image.new('RGBA', (32, 48), (200, 120, 80, 255)).save(reference)
            provider = MockImageProvider()
            provider.validate_request(self._request(task='image_to_image', reference=str(reference)))

    def test_image_adapter_binds_text_to_image_without_stale_attachment(self) -> None:
        with TemporaryDirectory() as temp_dir:
            template = Path(temp_dir) / 'image.json'
            template.write_text(json.dumps({'model_type': 'image', 'image_start': ['old.png']}), encoding='utf-8')
            config = LocalWanGPImageConfig(settings_template=str(template))
            request = self._request()
            request.provider = 'local_wangp_image'
            payload = WanGPImageSettingsAdapter().build_payload(request, config, {'reference_image': None, 'output_directory': temp_dir})
            self.assertNotIn('image_start', payload)
            self.assertEqual(payload['prompt'], request.positive_prompt)
            self.assertEqual(payload['negative_prompt'], request.negative_prompt)
            self.assertEqual(payload['resolution'], '128x96')
            self.assertEqual(payload['num_inference_steps'], 8)

    def test_image_adapter_binds_image_to_image_reference(self) -> None:
        with TemporaryDirectory() as temp_dir:
            template = Path(temp_dir) / 'image.json'
            template.write_text(json.dumps({'model_type': 'image', 'image_start': []}), encoding='utf-8')
            reference = Path(temp_dir) / 'master.png'
            Image.new('RGB', (16, 16), (1, 2, 3)).save(reference)
            config = LocalWanGPImageConfig(settings_template=str(template))
            request = self._request(task='image_to_image', reference=str(reference))
            request.provider = 'local_wangp_image'
            payload = WanGPImageSettingsAdapter().build_payload(
                request,
                config,
                {'reference_image': str(reference), 'output_directory': temp_dir},
            )
            self.assertEqual(payload['image_start'], [str(reference)])

    def test_local_image_output_normalization_is_png(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / 'wan-output.webp'
            target = Path(temp_dir) / 'generated_image.png'
            Image.new('RGB', (77, 55), (20, 40, 60)).save(source, format='WEBP')
            metadata = LocalWanGPImageProvider._normalize_and_validate_image(source, target)
            self.assertTrue(target.is_file())
            self.assertEqual(metadata['width'], 77)
            self.assertEqual(metadata['height'], 55)
            with Image.open(target) as image:
                self.assertEqual(image.format, 'PNG')

    def test_find_output_image_prefers_available_image(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            Image.new('RGB', (10, 10), (1, 2, 3)).save(root / 'a.png')
            found = LocalWanGPImageProvider._find_output_image(root)
            self.assertEqual(found.name, 'a.png')

    def test_project_schema_contains_image_generation_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = ProjectStore.create(Path(temp_dir) / 'project', name='Test')
            payload = store.load()
            self.assertIn('image_generation', payload['pipeline_state'])
            self.assertIn('generated_image', payload['assets'])
            self.assertIn('image_generation_manifest', payload['assets'])

    def test_direction_group_contains_image_generation_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = ProjectStore.create(Path(temp_dir) / 'project', name='Test')
            subject = store.create_group(group_type='subject', name='Hero')
            animation = store.create_group(group_type='animation', name='Walk', parent_id=subject['id'])
            direction = store.create_group(group_type='direction', name='SE', parent_id=animation['id'])
            self.assertIn('image_generation', direction['pipeline_state'])
            self.assertIn('generated_image', direction['assets'])


if __name__ == '__main__':
    unittest.main()
