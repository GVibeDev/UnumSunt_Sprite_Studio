from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.krea_compliance import (
    KREA_AUP_URL,
    KREA_LICENSE_URL,
    has_valid_review_record,
    krea_policy_applies,
    settings_model_type,
    write_review_record,
)
from app.version import APP_LICENSE, APP_VERSION


class R5c7ReleaseComplianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_core_license_is_gpl3_or_later(self):
        self.assertEqual(APP_VERSION, 'R5c8')
        self.assertEqual(APP_LICENSE, 'GPL-3.0-or-later')
        license_text = (self.root / 'LICENSE').read_text(encoding='utf-8')
        self.assertIn('GNU GENERAL PUBLIC LICENSE', license_text)
        self.assertIn('Version 3, 29 June 2007', license_text)

    def test_third_party_notice_keeps_ai_licenses_separate(self):
        notice = (self.root / 'THIRD_PARTY_NOTICES.txt').read_text(encoding='utf-8')
        self.assertIn('WanGP Community License 2.0', notice)
        self.assertIn('Krea 2 Community License Agreement v.1', notice)
        self.assertIn('not relicensed under the Sprite Studio GPL', notice)
        self.assertIn('6e35b37e309ccebeed193ef53cdff66fb973b693', notice)
        self.assertIn('f7a3040b990b672af3c30b5ad1f0df8ffd244881', notice)

    def test_installer_displays_gpl_information_without_forced_acceptance(self):
        iss = (self.root / 'installer' / 'UnumSuntSpriteStudio_R5c8.iss').read_text(encoding='utf-8')
        self.assertIn('InfoBeforeFile=..\\OPEN_SOURCE_LICENSE_NOTICE.txt', iss)
        self.assertNotIn('LicenseFile=..\\LICENSE', iss)

    def test_pyinstaller_bundles_legal_material(self):
        spec = (self.root / 'UnumSuntSpriteStudio.spec').read_text(encoding='utf-8')
        self.assertIn("('LICENSE', '.')", spec)
        self.assertIn("('OPEN_SOURCE_LICENSE_NOTICE.txt', '.')", spec)
        self.assertIn("('THIRD_PARTY_NOTICES.txt', '.')", spec)
        self.assertIn("('KREA_SAFETY_AND_USE.txt', '.')", spec)
        self.assertIn("('build/legal', 'licenses')", spec)
        self.assertIn(' + legal_datas', spec)

    def test_build_collects_licenses_from_actual_build_environment(self):
        build = (self.root / 'build_windows_standalone.ps1').read_text(encoding='utf-8')
        self.assertIn('tools\\collect_release_licenses.py --output build\\legal', build)
        collector = (self.root / 'tools' / 'collect_release_licenses.py').read_text(encoding='utf-8')
        for package in ('PySide6', 'opencv-python', 'numpy', 'Pillow', 'PyInstaller'):
            self.assertIn(f'"{package}"', collector)

    def test_runtime_manifest_uses_official_krea_policy_urls(self):
        payload = json.loads((self.root / 'assets' / 'runtime' / 'runtime_components.json').read_text(encoding='utf-8'))
        krea = payload['models']['krea2_turbo']
        self.assertEqual(krea['license_url'], KREA_LICENSE_URL)
        self.assertEqual(krea['aup_url'], KREA_AUP_URL)
        self.assertEqual(krea['revision'], 'f7a3040b990b672af3c30b5ad1f0df8ffd244881')

    def test_krea_template_detection_reads_model_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'settings.json'
            path.write_text(json.dumps({'model_type': 'krea2_turbo'}), encoding='utf-8')
            self.assertEqual(settings_model_type(path), 'krea2_turbo')
            self.assertTrue(krea_policy_applies(path))
            path.write_text(json.dumps({'model_type': 'other_model'}), encoding='utf-8')
            self.assertFalse(krea_policy_applies(path))

    def test_krea_review_record_roundtrip_is_minimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'image_generation_manifest.json'
            manifest.write_text('{}', encoding='utf-8')
            image = root / 'output.png'
            image.write_bytes(b'png')
            record = write_review_record(manifest_path=manifest, image_path=image)
            self.assertIsNotNone(record)
            self.assertTrue(has_valid_review_record(manifest_path=manifest, image_path=image))
            payload = json.loads(Path(record).read_text(encoding='utf-8'))
            self.assertTrue(payload['reviewed'])
            self.assertEqual(payload['license_url'], KREA_LICENSE_URL)
            self.assertEqual(payload['aup_url'], KREA_AUP_URL)
            self.assertNotIn('prompt', payload)
            self.assertNotIn('token', payload)
            self.assertNotIn('user', payload)

    def test_image_workspace_has_pre_and_post_generation_krea_gates(self):
        source = (self.root / 'app' / 'image_generation_workspace.py').read_text(encoding='utf-8')
        self.assertIn('krea_prompt_attestation', source)
        self.assertIn('current_job_requires_krea_review', source)
        self.assertIn('last_image_requires_krea_review', source)
        self.assertIn('write_review_record', source)
        self.assertIn('Krea 2 review required', source)
        self.assertIn('Non-Krea providers retain the original R5e9 immediate hand-off contract.', source)


if __name__ == '__main__':
    unittest.main()
