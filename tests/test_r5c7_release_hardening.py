from __future__ import annotations

import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from app.runtime_installer import RuntimeInstallError, RuntimeInstaller, load_runtime_components_manifest
from app.version import APP_VERSION, WINDOWS_PRODUCT_VERSION


class R5c7ReleaseHardeningTests(unittest.TestCase):
    def test_version_identity_is_r5c7(self):
        self.assertEqual(APP_VERSION, "R5c8")
        self.assertEqual(WINDOWS_PRODUCT_VERSION, "5.8.0.0")

    def test_wangp_and_krea_revisions_are_immutable(self):
        manifest = load_runtime_components_manifest()
        self.assertRegex(manifest.wangp_revision, r"^[0-9a-f]{40}$")
        self.assertIn(manifest.wangp_revision, manifest.wangp_archive_url)
        self.assertNotIn("/heads/main", manifest.wangp_archive_url)
        krea = manifest.models["krea2_turbo"]
        self.assertRegex(krea.revision, r"^[0-9a-f]{40}$")
        self.assertIn(krea.revision, krea.wan_default_url)

    def test_krea_template_uses_pinned_revision(self):
        root = Path(__file__).resolve().parents[1]
        manifest = load_runtime_components_manifest()
        payload = json.loads((root / "assets/runtime/krea2_turbo_settings_template.json").read_text(encoding="utf-8"))
        self.assertIn(manifest.models["krea2_turbo"].revision, payload["model_filename"])
        self.assertNotIn("/resolve/main/", payload["model_filename"])

    def test_safe_zip_extract_accepts_normal_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "ok.zip"
            out = root / "out"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Wan2GP-test/wgp.py", "print('ok')")
            RuntimeInstaller._safe_extract_zip(archive, out)
            self.assertEqual((out / "Wan2GP-test/wgp.py").read_text(encoding="utf-8"), "print('ok')")

    def test_safe_zip_extract_rejects_parent_traversal_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad.zip"
            out = root / "out"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Wan2GP-test/good.txt", "good")
                zf.writestr("../escape.txt", "bad")
            with self.assertRaises(RuntimeInstallError):
                RuntimeInstaller._safe_extract_zip(archive, out)
            self.assertFalse((root / "escape.txt").exists())
            self.assertFalse((out / "Wan2GP-test/good.txt").exists())

    def test_safe_zip_extract_rejects_windows_drive_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad-drive.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("C:/Windows/evil.txt", "bad")
            with self.assertRaises(RuntimeInstallError):
                RuntimeInstaller._safe_extract_zip(archive, root / "out")

    def test_safe_zip_extract_rejects_symlink_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad-link.zip"
            info = zipfile.ZipInfo("Wan2GP-test/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr(info, "../../outside")
            with self.assertRaises(RuntimeInstallError):
                RuntimeInstaller._safe_extract_zip(archive, root / "out")

    def test_pillow_deprecated_fromarray_mode_is_removed(self):
        root = Path(__file__).resolve().parents[1]
        export_service = (root / "app/export_service.py").read_text(encoding="utf-8")
        image_provider = (root / "app/generation/image_provider.py").read_text(encoding="utf-8")
        self.assertNotIn('Image.fromarray(rgba, mode="RGBA")', export_service)
        self.assertNotIn("Image.fromarray(canvas, 'RGB')", image_provider)

    def test_gitignore_guards_release_secrets_and_models(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / ".gitignore").read_text(encoding="utf-8")
        for token in (".env", ".build-venv/", "release/", "*.safetensors", "*.gguf", "local_wangp_image.json"):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
