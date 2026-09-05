from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

VIDEO_EXTENSIONS = frozenset({'.mp4', '.m4v', '.mov', '.avi', '.webm'})
IMAGE_EXTENSIONS = frozenset({'.png', '.webp', '.bmp', '.tif', '.tiff'})
SEQUENCE_MANIFEST_EXTENSIONS = frozenset({'.json'})


def classify_create_source_path(path: str | Path) -> str | None:
    suffix = Path(path).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return 'video'
    if suffix in IMAGE_EXTENSIONS:
        return 'spritesheet'
    if suffix in SEQUENCE_MANIFEST_EXTENSIONS:
        return 'sequence_manifest'
    return None


def import_dropped_create_source(
    paths: Iterable[str],
    *,
    open_video: Callable[[str], bool],
    open_spritesheet: Callable[[str], bool],
    open_sequence_manifest: Callable[[str], bool],
    navigate: Callable[[str], None],
    show_canvas: Callable[[], None],
    status: Callable[[str], None],
) -> bool:
    """Route one dropped local source through the already validated import paths.

    This is an adapter only. It does not decode media, slice sheets, mutate
    ProjectStore directly or duplicate any import implementation.
    """

    candidates = [Path(value).expanduser() for value in paths if str(value).strip()]
    source = next(
        (candidate for candidate in candidates if candidate.is_file() and classify_create_source_path(candidate)),
        None,
    )
    if source is None:
        status('CREATE Canvas: no supported local source was dropped.')
        return False

    source = source.resolve()
    kind = classify_create_source_path(source)
    opened = False
    route_id = 'extraction'
    if kind == 'video':
        opened = bool(open_video(str(source)))
    elif kind == 'spritesheet':
        opened = bool(open_spritesheet(str(source)))
        route_id = 'spritesheet'
    elif kind == 'sequence_manifest':
        opened = bool(open_sequence_manifest(str(source)))
    if not opened:
        return False

    navigate(route_id)
    show_canvas()
    status(f'CREATE Canvas source loaded: {source.name}')
    return True
