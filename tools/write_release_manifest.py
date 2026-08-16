from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: write_release_manifest.py <dist_dir> <output_json>')
        return 2
    dist = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    files = []
    for path in sorted(item for item in dist.rglob('*') if item.is_file()):
        files.append({
            'path': path.relative_to(dist).as_posix(),
            'bytes': path.stat().st_size,
            'sha256': sha256(path),
        })
    payload = {
        'application': 'Unum Sunt Sprite Studio',
        'version': 'R5c1',
        'milestone': 'Windows Standalone Core',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'distribution_mode': 'PyInstaller onedir x64',
        'python_required_on_target': False,
        'ai_runtime_bundled': False,
        'files': files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
