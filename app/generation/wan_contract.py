from __future__ import annotations

from dataclasses import dataclass
from math import gcd
import json
from pathlib import Path
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class WanResolutionOption:
    """A concrete WanGP resolution exposed through a class/aspect contract."""

    resolution_class: str
    aspect_ratio: str
    width: int
    height: int
    label: str
    source: str = "builtin"

    @property
    def value(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def key(self) -> tuple[str, str]:
        return self.resolution_class, self.aspect_ratio

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution_class": self.resolution_class,
            "aspect_ratio": self.aspect_ratio,
            "width": self.width,
            "height": self.height,
            "value": self.value,
            "label": self.label,
            "source": self.source,
        }


# R5b1c intentionally binds to explicit dimensions.  These values cover the
# native classes used during the real WanGP validation campaign.  A local
# resolutions.json in the WanGP root can override or extend this table.
_BUILTIN_RESOLUTIONS: tuple[WanResolutionOption, ...] = (
    WanResolutionOption("360p", "16:9", 576, 320, "576x320 (16:9, 360p)"),
    WanResolutionOption("360p", "9:16", 320, 576, "320x576 (9:16, 360p)"),
    WanResolutionOption("360p", "1:1", 448, 448, "448x448 (1:1, 360p)"),
    WanResolutionOption("360p", "4:3", 512, 384, "512x384 (4:3, 360p)"),
    WanResolutionOption("360p", "3:4", 384, 512, "384x512 (3:4, 360p)"),
    WanResolutionOption("480p", "16:9", 832, 480, "832x480 (16:9, 480p)"),
    WanResolutionOption("480p", "9:16", 480, 832, "480x832 (9:16, 480p)"),
    WanResolutionOption("480p", "1:1", 720, 720, "720x720 (1:1, 480p)"),
    WanResolutionOption("480p", "4:3", 832, 624, "832x624 (4:3, 480p)"),
    WanResolutionOption("480p", "3:4", 624, 832, "624x832 (3:4, 480p)"),
    WanResolutionOption("720p", "16:9", 1280, 720, "1280x720 (16:9, 720p)"),
    WanResolutionOption("720p", "9:16", 720, 1280, "720x1280 (9:16, 720p)"),
    WanResolutionOption("720p", "1:1", 1024, 1024, "1024x1024 (1:1, 720p)"),
    WanResolutionOption("720p", "4:3", 1104, 832, "1104x832 (4:3, 720p)"),
    WanResolutionOption("720p", "3:4", 832, 1104, "832x1104 (3:4, 720p)"),
)

_RESOLUTION_RE = re.compile(r"^\s*(?P<width>\d+)\s*[xX]\s*(?P<height>\d+)\s*$")
_CLASS_RE = re.compile(r"(?<!\d)(?P<class>\d{3,4})\s*p\b", re.IGNORECASE)
_RATIO_RE = re.compile(r"(?P<a>\d+)\s*:\s*(?P<b>\d+)")


def builtin_resolution_options() -> list[WanResolutionOption]:
    return list(_BUILTIN_RESOLUTIONS)


def parse_resolution(value: str) -> tuple[int, int] | None:
    match = _RESOLUTION_RE.match(str(value or ""))
    if not match:
        return None
    width = int(match.group("width"))
    height = int(match.group("height"))
    if width <= 0 or height <= 0:
        return None
    return width, height


def infer_aspect_ratio(width: int, height: int, label: str = "") -> str:
    label_match = _RATIO_RE.search(label)
    if label_match:
        return f"{int(label_match.group('a'))}:{int(label_match.group('b'))}"
    divisor = gcd(max(1, int(width)), max(1, int(height)))
    return f"{int(width) // divisor}:{int(height) // divisor}"


def infer_resolution_class(width: int, height: int, label: str = "") -> str:
    label_match = _CLASS_RE.search(label)
    if label_match:
        return f"{int(label_match.group('class'))}p"

    exact = next((option for option in _BUILTIN_RESOLUTIONS if option.width == width and option.height == height), None)
    if exact:
        return exact.resolution_class
    return "Custom"


def option_from_value(value: str, *, label: str | None = None, source: str = "custom") -> WanResolutionOption | None:
    dimensions = parse_resolution(value)
    if dimensions is None:
        return None
    width, height = dimensions
    display_label = str(label or f"{width}x{height}")
    return WanResolutionOption(
        resolution_class=infer_resolution_class(width, height, display_label),
        aspect_ratio=infer_aspect_ratio(width, height, display_label),
        width=width,
        height=height,
        label=display_label,
        source=source,
    )


def load_custom_resolution_options(wangp_root: str | Path | None) -> list[WanResolutionOption]:
    if not wangp_root:
        return []
    path = Path(wangp_root).expanduser() / "resolutions.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []

    options: list[WanResolutionOption] = []
    for item in payload:
        if not isinstance(item, list) or len(item) != 2:
            continue
        label, value = item
        option = option_from_value(str(value), label=str(label), source=str(path))
        if option is None:
            continue
        if option.width % 16 != 0 or option.height % 16 != 0:
            continue
        options.append(option)
    return options


def template_resolution_option(template_path: str | Path | None) -> WanResolutionOption | None:
    if not template_path:
        return None
    path = Path(template_path).expanduser()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("resolution")
    if not isinstance(value, str):
        return None
    return option_from_value(value, label=f"{value} (preset)", source=str(path))


def merged_resolution_options(
    wangp_root: str | Path | None = None,
    template_path: str | Path | None = None,
) -> list[WanResolutionOption]:
    """Return one authoritative option for each class/aspect pair.

    Built-ins provide a stable fallback.  A WanGP resolutions.json overrides
    matching class/aspect pairs.  The current template resolution is retained
    even when it is not represented by either source.
    """

    by_key: dict[tuple[str, str], WanResolutionOption] = {
        option.key: option for option in builtin_resolution_options()
    }
    for option in load_custom_resolution_options(wangp_root):
        by_key[option.key] = option

    template_option = template_resolution_option(template_path)
    if template_option is not None:
        existing = by_key.get(template_option.key)
        if existing is None or existing.value != template_option.value:
            # Keep a distinct custom class when a template reuses a familiar
            # aspect but points to a different concrete dimension.
            if existing is not None:
                template_option = WanResolutionOption(
                    resolution_class=f"Preset {template_option.value}",
                    aspect_ratio=template_option.aspect_ratio,
                    width=template_option.width,
                    height=template_option.height,
                    label=template_option.label,
                    source=template_option.source,
                )
            by_key[template_option.key] = template_option

    class_order = {"360p": 0, "480p": 1, "540p": 2, "720p": 3, "900p": 4, "1080p": 5, "Custom": 99}
    ratio_order = {"16:9": 0, "9:16": 1, "1:1": 2, "4:3": 3, "3:4": 4}
    return sorted(
        by_key.values(),
        key=lambda option: (
            class_order.get(option.resolution_class, 50),
            option.resolution_class,
            ratio_order.get(option.aspect_ratio, 50),
            option.aspect_ratio,
            option.width,
            option.height,
        ),
    )


def normalize_wan_frame_count(requested_frames: int) -> int:
    """Normalize to the greatest positive 4n+1 frame count not above input."""

    requested = max(1, int(requested_frames))
    if requested <= 1:
        return 1
    return max(1, requested - ((requested - 1) % 4))


@dataclass(frozen=True)
class WanFpsContract:
    requested_fps: float
    effective_fps: float | None
    source: str
    force_fps: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_fps": float(self.requested_fps),
            "effective_fps": None if self.effective_fps is None else float(self.effective_fps),
            "source": self.source,
            "force_fps": self.force_fps,
        }


def read_force_fps(template_path: str | Path | None) -> str:
    if not template_path:
        return ""
    path = Path(template_path).expanduser()
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    value = payload.get("force_fps", "")
    return str(value or "").strip()


def resolve_fps_contract(
    requested_fps: float,
    force_fps: str,
    control_video_fps: float | None = None,
) -> WanFpsContract:
    force = str(force_fps or "").strip()
    lower = force.lower()
    if lower == "control":
        return WanFpsContract(
            requested_fps=float(requested_fps),
            effective_fps=float(control_video_fps) if control_video_fps and control_video_fps > 0 else None,
            source="control_video" if control_video_fps and control_video_fps > 0 else "control_video_unresolved",
            force_fps=force,
        )
    if force:
        try:
            numeric = float(force)
        except ValueError:
            numeric = 0.0
        if numeric > 0:
            return WanFpsContract(
                requested_fps=float(requested_fps),
                effective_fps=numeric,
                source="preset_force_fps",
                force_fps=force,
            )
    return WanFpsContract(
        requested_fps=float(requested_fps),
        effective_fps=float(requested_fps),
        source="request",
        force_fps=force,
    )


def option_for_selection(
    options: Iterable[WanResolutionOption],
    resolution_class: str,
    aspect_ratio: str,
) -> WanResolutionOption | None:
    return next(
        (
            option
            for option in options
            if option.resolution_class == resolution_class and option.aspect_ratio == aspect_ratio
        ),
        None,
    )
