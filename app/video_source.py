from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from app.models import VideoMetadata
from app.spritesheet_import import load_sequence_manifest


class VideoOpenError(RuntimeError):
    """Raised when a video or imported frame sequence cannot be opened or decoded."""


class VideoSource:
    def __init__(self, cache_size: int = 18) -> None:
        self._capture: cv2.VideoCapture | None = None
        self._metadata: VideoMetadata | None = None
        self._cache_size = max(1, cache_size)
        self._cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self._rgba_cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self._sequence_paths: list[Path] = []
        self._source_kind: str | None = None
        self._sequence_manifest_path: Path | None = None

    @property
    def metadata(self) -> VideoMetadata:
        if self._metadata is None:
            raise VideoOpenError('No source is open.')
        return self._metadata

    @property
    def is_open(self) -> bool:
        if self._source_kind == 'sequence':
            return self._metadata is not None and bool(self._sequence_paths)
        return self._capture is not None and self._capture.isOpened()

    @property
    def source_kind(self) -> str | None:
        return self._source_kind

    @property
    def sequence_manifest_path(self) -> Path | None:
        return self._sequence_manifest_path

    def open(self, path: str | Path) -> VideoMetadata:
        self.close()
        video_path = Path(path).expanduser().resolve()
        if not video_path.exists() or not video_path.is_file():
            raise VideoOpenError(f'Video file does not exist: {video_path}')

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            capture.release()
            raise VideoOpenError(
                'Unable to open the video. Check the codec, file integrity, and OpenCV installation.'
            )

        width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
        height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))

        if width <= 0 or height <= 0:
            capture.release()
            raise VideoOpenError('The video does not report valid dimensions.')
        if fps <= 0 or fps > 1000:
            capture.release()
            raise VideoOpenError('The video does not report a valid frame rate.')
        if frame_count <= 0:
            capture.release()
            raise VideoOpenError('The video does not report a valid frame count.')

        self._capture = capture
        self._metadata = VideoMetadata(
            path=video_path,
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
        )
        self._source_kind = 'video'
        self._cache.clear()
        self._rgba_cache.clear()

        # Decode the first frame immediately so failure is reported at open time.
        self.get_frame_rgb(0)
        return self._metadata

    def open_frame_sequence(
        self,
        frame_paths: Sequence[str | Path],
        *,
        fps: float = 12.0,
        source_path: str | Path | None = None,
        manifest_path: str | Path | None = None,
    ) -> VideoMetadata:
        self.close()
        paths = [Path(value).expanduser().resolve() for value in frame_paths]
        if not paths:
            raise VideoOpenError('The sequence contains no frames.')
        for path in paths:
            if not path.exists() or not path.is_file():
                raise VideoOpenError(f'Sequence frame does not exist: {path}')
        fps = float(fps)
        if fps <= 0 or fps > 1000:
            raise VideoOpenError('Invalid sequence FPS.')

        first = cv2.imread(str(paths[0]), cv2.IMREAD_UNCHANGED)
        if first is None:
            raise VideoOpenError(f'Unable to read frame: {paths[0]}')
        height, width = first.shape[:2]
        if width <= 0 or height <= 0:
            raise VideoOpenError('Invalid sequence frame dimensions.')
        # The existing R1/R2/R3 pipeline requires one stable source geometry.
        for path in paths[1:]:
            image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if image is None:
                raise VideoOpenError(f'Unable to read frame: {path}')
            if image.shape[:2] != (height, width):
                raise VideoOpenError(
                    f'Frame with incompatible dimensions: {path.name} = {image.shape[1]}×{image.shape[0]}, expected {width}×{height}.'
                )

        logical_path = Path(source_path).expanduser().resolve() if source_path is not None else paths[0]
        self._sequence_paths = paths
        self._source_kind = 'sequence'
        self._sequence_manifest_path = Path(manifest_path).expanduser().resolve() if manifest_path is not None else None
        self._metadata = VideoMetadata(
            path=logical_path,
            width=width,
            height=height,
            fps=fps,
            frame_count=len(paths),
        )
        self._cache.clear()
        self._rgba_cache.clear()
        self.get_frame_rgb(0)
        return self._metadata

    def open_sequence_manifest(self, manifest_path: str | Path) -> VideoMetadata:
        try:
            payload = load_sequence_manifest(manifest_path)
        except Exception as exc:
            raise VideoOpenError(f'Invalid sequence manifest: {exc}') from exc
        source_path = payload.get('source_sheet') or payload['manifest_path']
        return self.open_frame_sequence(
            payload['frame_paths'],
            fps=float(payload.get('fps', 12.0)),
            source_path=source_path,
            manifest_path=payload['manifest_path'],
        )

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self._metadata = None
        self._cache.clear()
        self._rgba_cache.clear()
        self._sequence_paths = []
        self._source_kind = None
        self._sequence_manifest_path = None

    def _cache_put(self, cache: OrderedDict[int, np.ndarray], index: int, value: np.ndarray) -> None:
        cache[index] = value.copy()
        cache.move_to_end(index)
        while len(cache) > self._cache_size:
            cache.popitem(last=False)

    def get_frame_rgba(self, frame_index: int) -> np.ndarray:
        if not self.is_open:
            raise VideoOpenError('No source is open.')
        metadata = self.metadata
        index = min(max(int(frame_index), 0), metadata.frame_count - 1)
        cached = self._rgba_cache.get(index)
        if cached is not None:
            self._rgba_cache.move_to_end(index)
            return cached.copy()

        if self._source_kind == 'sequence':
            raw = cv2.imread(str(self._sequence_paths[index]), cv2.IMREAD_UNCHANGED)
            if raw is None:
                raise VideoOpenError(f'Unable to decode imported frame {index}.')
            if raw.ndim == 2:
                rgb = cv2.cvtColor(raw, cv2.COLOR_GRAY2RGB)
                alpha = np.full(rgb.shape[:2] + (1,), 255, dtype=np.uint8)
                rgba = np.concatenate([rgb, alpha], axis=2)
            elif raw.shape[2] == 4:
                rgba = cv2.cvtColor(raw, cv2.COLOR_BGRA2RGBA)
            elif raw.shape[2] == 3:
                rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
                alpha = np.full(rgb.shape[:2] + (1,), 255, dtype=np.uint8)
                rgba = np.concatenate([rgb, alpha], axis=2)
            else:
                raise VideoOpenError(f'Unsupported imported frame format: {self._sequence_paths[index]}')
        else:
            rgb = self.get_frame_rgb(index)
            alpha = np.full(rgb.shape[:2] + (1,), 255, dtype=np.uint8)
            rgba = np.concatenate([rgb, alpha], axis=2)
        self._cache_put(self._rgba_cache, index, rgba)
        return rgba.copy()

    def get_frame_rgb(self, frame_index: int) -> np.ndarray:
        if not self.is_open:
            raise VideoOpenError('No source is open.')

        metadata = self.metadata
        index = min(max(int(frame_index), 0), metadata.frame_count - 1)

        cached = self._cache.get(index)
        if cached is not None:
            self._cache.move_to_end(index)
            return cached.copy()

        if self._source_kind == 'sequence':
            rgba = self.get_frame_rgba(index)
            # RGB view for R1 diagnostics. Existing alpha is preserved separately as an override.
            rgb = rgba[:, :, :3].copy()
            self._cache_put(self._cache, index, rgb)
            return rgb

        if self._capture is None:
            raise VideoOpenError('No video is open.')
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame_bgr = self._capture.read()
        if not ok or frame_bgr is None:
            raise VideoOpenError(f'Unable to decode frame {index}.')

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        self._cache_put(self._cache, index, frame_rgb)
        return frame_rgb.copy()
