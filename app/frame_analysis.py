from __future__ import annotations

from dataclasses import dataclass, field
from math import exp
from typing import Iterable, Sequence

import cv2
import numpy as np

from app.chroma_key import apply_chroma_key
from app.models import ChromaKeySettings


PROFILE_DEFAULTS: dict[str, int] = {
    "idle": 4,
    "walk": 8,
    "run": 8,
    "interact": 6,
}


@dataclass
class FrameFeature:
    frame_index: int
    time_seconds: float
    bbox: tuple[int, int, int, int]
    area_ratio: float
    centroid_x: float
    centroid_y: float
    width_ratio: float
    height_ratio: float
    edge_density: float
    descriptor: np.ndarray = field(repr=False)
    motion_from_previous: float = 0.0
    anomaly_score: float = 0.0
    quality_score: float = 1.0
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "frame_index": int(self.frame_index),
            "time_seconds": round(float(self.time_seconds), 6),
            "bbox": list(self.bbox),
            "area_ratio": round(float(self.area_ratio), 8),
            "centroid": [
                round(float(self.centroid_x), 8),
                round(float(self.centroid_y), 8),
            ],
            "size_ratio": [
                round(float(self.width_ratio), 8),
                round(float(self.height_ratio), 8),
            ],
            "edge_density": round(float(self.edge_density), 8),
            "motion_from_previous": round(float(self.motion_from_previous), 8),
            "anomaly_score": round(float(self.anomaly_score), 6),
            "quality_score": round(float(self.quality_score), 6),
            "flags": list(self.flags),
        }


@dataclass
class SmartSelectionResult:
    profile: str
    desired_count: int
    duplicate_threshold: float
    features: list[FrameFeature]
    suggestions: list[int]
    duplicate_pairs: list[tuple[int, int, float]]
    loop_score: float
    motion_total: float

    @property
    def anomaly_count(self) -> int:
        return sum(1 for feature in self.features if feature.anomaly_score >= 3.5)

    def to_dict(self) -> dict:
        return {
            "schema": "unum-sunt-smart-frame-analysis-v1",
            "profile": self.profile,
            "desired_count": self.desired_count,
            "duplicate_threshold": round(self.duplicate_threshold, 8),
            "suggestions": list(self.suggestions),
            "summary": {
                "analyzed_frames": len(self.features),
                "suggested_frames": len(self.suggestions),
                "duplicate_pairs": len(self.duplicate_pairs),
                "anomaly_frames": self.anomaly_count,
                "loop_score": round(self.loop_score, 6),
                "motion_total": round(self.motion_total, 6),
            },
            "duplicates": [
                {
                    "first": first,
                    "second": second,
                    "distance": round(distance, 8),
                }
                for first, second, distance in self.duplicate_pairs
            ],
            "frames": [feature.to_dict() for feature in self.features],
        }


def sensitivity_to_duplicate_threshold(sensitivity: int) -> float:
    normalized = np.clip(int(sensitivity), 0, 100) / 100.0
    return float(0.0005 + normalized * 0.0300)


def extract_frame_feature(
    *,
    frame_index: int,
    time_seconds: float,
    image_rgb: np.ndarray,
    chroma_settings: ChromaKeySettings,
    descriptor_size: int = 32,
) -> FrameFeature:
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError('The source frame must be RGB.')

    rgba, alpha = apply_chroma_key(image_rgb, chroma_settings)
    binary = alpha > 24
    ys, xs = np.nonzero(binary)
    if len(xs) == 0:
        raise ValueError(
            f'No detectable subject in frame {frame_index}. Fix the chroma settings before analysis.'
        )

    height, width = alpha.shape
    left = int(xs.min())
    top = int(ys.min())
    right = int(xs.max()) + 1
    bottom = int(ys.max()) + 1
    bbox_width = right - left
    bbox_height = bottom - top

    weights = alpha[ys, xs].astype(np.float64)
    weight_sum = float(weights.sum())
    if weight_sum <= 0:
        centroid_x = float(xs.mean() / max(1, width))
        centroid_y = float(ys.mean() / max(1, height))
    else:
        centroid_x = float(
            np.average(xs.astype(np.float64), weights=weights) / max(1, width)
        )
        centroid_y = float(
            np.average(ys.astype(np.float64), weights=weights) / max(1, height)
        )

    area_ratio = float(binary.sum() / binary.size)
    width_ratio = float(bbox_width / max(1, width))
    height_ratio = float(bbox_height / max(1, height))

    crop_rgba = rgba[top:bottom, left:right]
    crop_alpha = crop_rgba[:, :, 3].astype(np.float32) / 255.0
    crop_rgb = crop_rgba[:, :, :3].astype(np.float32) / 255.0
    luminance = (
        crop_rgb[:, :, 0] * 0.2126
        + crop_rgb[:, :, 1] * 0.7152
        + crop_rgb[:, :, 2] * 0.0722
    )
    premultiplied_luminance = luminance * crop_alpha

    descriptor_dim = max(8, min(96, int(descriptor_size)))
    interpolation = (
        cv2.INTER_AREA
        if bbox_width > descriptor_dim or bbox_height > descriptor_dim
        else cv2.INTER_LINEAR
    )
    resized_alpha = cv2.resize(
        crop_alpha,
        (descriptor_dim, descriptor_dim),
        interpolation=interpolation,
    )
    resized_luminance = cv2.resize(
        premultiplied_luminance,
        (descriptor_dim, descriptor_dim),
        interpolation=interpolation,
    )
    descriptor = np.stack(
        (resized_alpha, resized_luminance),
        axis=2,
    ).astype(np.float32)

    edges = cv2.Canny(alpha, 48, 144)
    edge_density = float(
        np.count_nonzero(edges[top:bottom, left:right])
        / max(1, bbox_width * bbox_height)
    )

    return FrameFeature(
        frame_index=int(frame_index),
        time_seconds=float(time_seconds),
        bbox=(left, top, right, bottom),
        area_ratio=area_ratio,
        centroid_x=centroid_x,
        centroid_y=centroid_y,
        width_ratio=width_ratio,
        height_ratio=height_ratio,
        edge_density=edge_density,
        descriptor=descriptor,
    )


def feature_distance(first: FrameFeature, second: FrameFeature) -> float:
    descriptor_distance = float(
        np.mean(np.abs(first.descriptor - second.descriptor))
    )
    area_distance = abs(first.area_ratio - second.area_ratio)
    centroid_distance = float(
        np.hypot(
            first.centroid_x - second.centroid_x,
            first.centroid_y - second.centroid_y,
        )
    )
    size_distance = (
        abs(first.width_ratio - second.width_ratio)
        + abs(first.height_ratio - second.height_ratio)
    ) / 2.0
    edge_distance = abs(first.edge_density - second.edge_density)

    combined = (
        descriptor_distance * 0.68
        + area_distance * 0.08
        + centroid_distance * 0.09
        + size_distance * 0.10
        + edge_distance * 0.05
    )
    return float(np.clip(combined, 0.0, 1.0))


def _robust_z(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return np.zeros(0, dtype=np.float64)
    median = float(np.median(array))
    deviations = np.abs(array - median)
    mad = float(np.median(deviations))
    if mad < 1e-9:
        standard = float(np.std(array))
        if standard < 1e-9:
            return np.zeros_like(array)
        return deviations / standard
    return deviations / (1.4826 * mad)


def analyze_feature_sequence(
    features: Sequence[FrameFeature],
    duplicate_threshold: float,
) -> tuple[list[tuple[int, int, float]], float, float]:
    ordered = sorted(features, key=lambda feature: feature.frame_index)
    if not ordered:
        raise ValueError('No frames to analyze.')

    motions = [0.0]
    duplicate_pairs: list[tuple[int, int, float]] = []
    for previous, current in zip(ordered, ordered[1:]):
        distance = feature_distance(previous, current)
        motions.append(distance)
        if distance <= duplicate_threshold:
            duplicate_pairs.append(
                (previous.frame_index, current.frame_index, distance)
            )

    area_z = _robust_z([feature.area_ratio for feature in ordered])
    width_z = _robust_z([feature.width_ratio for feature in ordered])
    height_z = _robust_z([feature.height_ratio for feature in ordered])
    centroid_x_z = _robust_z([feature.centroid_x for feature in ordered])
    centroid_y_z = _robust_z([feature.centroid_y for feature in ordered])
    edge_z = _robust_z([feature.edge_density for feature in ordered])
    motion_z = _robust_z(motions)

    duplicate_second_frames = {second for _, second, _ in duplicate_pairs}

    for position, feature in enumerate(ordered):
        feature.motion_from_previous = float(motions[position])
        feature.flags.clear()

        shape_z = max(
            float(area_z[position]),
            float(width_z[position]),
            float(height_z[position]),
        )
        center_z = float(
            np.hypot(centroid_x_z[position], centroid_y_z[position])
        )
        detail_z = float(edge_z[position])
        transition_z = float(motion_z[position])

        anomaly = (
            shape_z * 0.42
            + center_z * 0.22
            + detail_z * 0.14
            + transition_z * 0.22
        )
        feature.anomaly_score = float(anomaly)
        feature.quality_score = float(np.clip(exp(-0.18 * anomaly), 0.0, 1.0))

        if shape_z >= 3.5:
            feature.flags.append("abnormal silhouette")
        if center_z >= 3.5:
            feature.flags.append('position drift')
        if detail_z >= 4.0:
            feature.flags.append("unstable detail")
        if position > 0 and transition_z >= 4.0:
            feature.flags.append("motion jump")
        if feature.frame_index in duplicate_second_frames:
            feature.flags.append("near duplicate")

    loop_distance = (
        feature_distance(ordered[0], ordered[-1])
        if len(ordered) > 1
        else 0.0
    )
    loop_score = float(np.clip(1.0 - loop_distance / 0.30, 0.0, 1.0))
    motion_total = float(sum(motions[1:]))
    return duplicate_pairs, loop_score, motion_total


def _profile_motion_weights(
    features: Sequence[FrameFeature],
    profile: str,
) -> np.ndarray:
    motions = np.asarray(
        [max(0.0, feature.motion_from_previous) for feature in features],
        dtype=np.float64,
    )
    if motions.size:
        motions[0] = 0.0

    positive = motions[motions > 1e-9]
    median_motion = float(np.median(positive)) if positive.size else 0.0

    if profile == "idle":
        floor = median_motion * 0.45
        return np.sqrt(np.maximum(motions, floor))
    if profile == "run":
        floor = median_motion * 0.10
        return np.power(np.maximum(motions, floor), 1.15)
    if profile == "interact":
        floor = median_motion * 0.20
        return np.maximum(motions, floor)
    floor = median_motion * 0.18
    return np.maximum(motions, floor)


def select_keyframes(
    features: Sequence[FrameFeature],
    *,
    desired_count: int,
    profile: str,
    duplicate_threshold: float,
    avoid_strong_anomalies: bool = True,
) -> list[int]:
    ordered = sorted(features, key=lambda feature: feature.frame_index)
    if not ordered:
        raise ValueError('No frames available.')
    desired = max(1, min(int(desired_count), len(ordered)))
    profile_key = profile.lower().strip()
    if profile_key not in PROFILE_DEFAULTS:
        raise ValueError(f'Unsupported profile: {profile}')

    candidates = [
        feature
        for feature in ordered
        if not avoid_strong_anomalies or feature.anomaly_score < 7.0
    ]
    if len(candidates) < desired:
        candidates = ordered.copy()
    if len(candidates) <= desired:
        return [feature.frame_index for feature in candidates]

    weights = _profile_motion_weights(candidates, profile_key)
    progression = np.cumsum(weights)
    progression -= progression[0]
    total = float(progression[-1])

    if total <= 1e-9:
        progression = np.linspace(0.0, 1.0, len(candidates))
        total = 1.0

    cyclic = profile_key in {"idle", "walk", "run"}
    if cyclic:
        targets = np.linspace(0.0, total, desired + 1)[:-1]
    else:
        targets = np.linspace(0.0, total, desired)

    selected_positions: list[int] = []

    def duplicate_penalty(candidate_pos: int) -> float:
        if not selected_positions:
            return 0.0
        candidate = candidates[candidate_pos]
        minimum = min(
            feature_distance(candidate, candidates[position])
            for position in selected_positions
        )
        if minimum <= duplicate_threshold:
            return 4.0 + (duplicate_threshold - minimum) * 20.0
        return 0.0

    for target in targets:
        best_position = None
        best_cost = float("inf")
        for position, feature in enumerate(candidates):
            if position in selected_positions:
                continue
            phase_cost = abs(float(progression[position]) - float(target)) / max(
                total,
                1e-9,
            )
            anomaly_cost = min(feature.anomaly_score, 12.0) * 0.025
            cost = phase_cost + anomaly_cost + duplicate_penalty(position)
            if cost < best_cost:
                best_cost = cost
                best_position = position
        if best_position is not None:
            selected_positions.append(best_position)

    while len(selected_positions) < desired:
        best_position = None
        best_score = -float("inf")
        for position, feature in enumerate(candidates):
            if position in selected_positions:
                continue
            if selected_positions:
                diversity = min(
                    feature_distance(feature, candidates[chosen])
                    for chosen in selected_positions
                )
                temporal = min(
                    abs(position - chosen) / max(1, len(candidates) - 1)
                    for chosen in selected_positions
                )
            else:
                diversity = 1.0
                temporal = 1.0
            score = (
                diversity * 0.68
                + temporal * 0.22
                + feature.quality_score * 0.10
            )
            if score > best_score:
                best_score = score
                best_position = position
        if best_position is None:
            break
        selected_positions.append(best_position)

    selected = sorted(
        candidates[position].frame_index
        for position in selected_positions[:desired]
    )
    return selected


def analyze_and_select(
    *,
    features: Sequence[FrameFeature],
    profile: str,
    desired_count: int,
    duplicate_threshold: float,
    avoid_strong_anomalies: bool = True,
) -> SmartSelectionResult:
    ordered = sorted(features, key=lambda feature: feature.frame_index)
    duplicates, loop_score, motion_total = analyze_feature_sequence(
        ordered,
        duplicate_threshold,
    )
    suggestions = select_keyframes(
        ordered,
        desired_count=desired_count,
        profile=profile,
        duplicate_threshold=duplicate_threshold,
        avoid_strong_anomalies=avoid_strong_anomalies,
    )
    return SmartSelectionResult(
        profile=profile,
        desired_count=desired_count,
        duplicate_threshold=duplicate_threshold,
        features=ordered,
        suggestions=suggestions,
        duplicate_pairs=duplicates,
        loop_score=loop_score,
        motion_total=motion_total,
    )
