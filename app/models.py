from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    width: int
    height: int
    fps: float
    frame_count: int

    @property
    def duration_seconds(self) -> float:
        if self.fps <= 0:
            return 0.0
        return self.frame_count / self.fps

    def frame_time_seconds(self, frame_index: int) -> float:
        if self.fps <= 0:
            return 0.0
        return max(0, frame_index) / self.fps


@dataclass
class BackgroundColorRule:
    rgb: tuple[int, int, int]
    enabled: bool = True
    tolerance: int | None = None

    def normalized_tolerance(self, fallback: int) -> int:
        value = fallback if self.tolerance is None else self.tolerance
        return max(0, min(255, int(value)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rgb": [int(v) for v in self.rgb],
            "enabled": bool(self.enabled),
            "tolerance": None if self.tolerance is None else int(self.tolerance),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackgroundColorRule":
        rgb = data.get("rgb", (0, 255, 0))
        if not isinstance(rgb, (list, tuple)) or len(rgb) != 3:
            raise ValueError("BackgroundColorRule.rgb deve contenere tre valori.")
        return cls(
            rgb=tuple(max(0, min(255, int(v))) for v in rgb),
            enabled=bool(data.get("enabled", True)),
            tolerance=(None if data.get("tolerance") is None else max(0, min(255, int(data.get("tolerance"))))),
        )


@dataclass
class ChromaKeySettings:
    background_rgb: tuple[int, int, int] = (0, 255, 0)
    tolerance: int = 28
    softness: int = 18
    cleanup_radius: int = 1
    edge_decontamination: int = 35
    keying_mode: str = "auto"
    requested_background_rgb: tuple[int, int, int] | None = None
    detected_background_rgb: tuple[int, int, int] | None = None
    background_distance: float | None = None
    background_mismatch: bool = False
    additional_background_colors: list[BackgroundColorRule] = field(default_factory=list)
    outer_border_mask_px: int = 0
    subject_edge_mask_expand_px: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["background_rgb"] = list(self.background_rgb)
        data["requested_background_rgb"] = (
            list(self.requested_background_rgb)
            if self.requested_background_rgb is not None
            else None
        )
        data["detected_background_rgb"] = (
            list(self.detected_background_rgb)
            if self.detected_background_rgb is not None
            else None
        )
        data["additional_background_colors"] = [rule.to_dict() for rule in self.additional_background_colors]
        return data


@dataclass
class ExportSettings:
    output_format: str = "png"
    crop_to_subject: bool = True
    padding: int = 8
    webp_quality: int = 95

    def normalized_format(self) -> str:
        value = self.output_format.lower().strip()
        if value not in {"png", "webp"}:
            raise ValueError(f"Formato non supportato: {self.output_format}")
        return value


@dataclass
class FrameAlignmentState:
    frame_index: int
    source_pivot_x: float
    source_pivot_y: float
    offset_x: int = 0
    offset_y: int = 0
    pivot_mode: str = "auto"
    anchor_mode: str = "ground"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "source_pivot": [
                round(float(self.source_pivot_x), 4),
                round(float(self.source_pivot_y), 4),
            ],
            "offset": [int(self.offset_x), int(self.offset_y)],
            "pivot_mode": self.pivot_mode,
            "anchor_mode": self.anchor_mode,
        }


@dataclass
class AlignmentSettings:
    canvas_width: int = 96
    canvas_height: int = 96
    canvas_pivot_x: float = 48.0
    canvas_pivot_y: float = 88.0
    margin: int = 4
    shared_scale: float = 1.0
    fps: int = 10
    loop: bool = True
    animation_name: str = 'walk'
    direction: str = 'south-east'

    def validate(self) -> None:
        if not 36 <= self.canvas_width <= 256 or not 36 <= self.canvas_height <= 256:
            raise ValueError("La tela output deve essere compresa tra 36×36 e 256×256 px, con larghezza e altezza indipendenti.")
        if not 0 <= self.canvas_pivot_x <= self.canvas_width:
            raise ValueError("Pivot X della tela fuori intervallo.")
        if not 0 <= self.canvas_pivot_y <= self.canvas_height:
            raise ValueError("Pivot Y della tela fuori intervallo.")
        if self.margin < 0:
            raise ValueError("Il margine non può essere negativo.")
        if self.shared_scale <= 0:
            raise ValueError("La scala deve essere positiva.")
        if self.fps <= 0:
            raise ValueError("Gli FPS devono essere positivi.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "size": [int(self.canvas_width), int(self.canvas_height)],
            "shape": ("square" if self.canvas_width == self.canvas_height else ("landscape" if self.canvas_width > self.canvas_height else "portrait")),
            "aspect_ratio": round(float(self.canvas_width) / float(self.canvas_height), 8),
            "supported_dimension_range": [36, 256],
            "pivot": [
                round(float(self.canvas_pivot_x), 4),
                round(float(self.canvas_pivot_y), 4),
            ],
            "margin": int(self.margin),
            "shared_scale": round(float(self.shared_scale), 8),
            "fps": int(self.fps),
            "loop": bool(self.loop),
        }
