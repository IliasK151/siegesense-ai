"""Descriptive screen-space motion estimates from local sampled gameplay frames.

This module estimates optical flow of visible image features. It does not measure
mouse input, world-space aim, recoil control, target tracking, or player skill.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MotionPair:
    start_timestamp_ms: int
    end_timestamp_ms: int
    tracked_feature_count: int
    median_dx_px: float
    median_dy_px: float
    median_motion_px: float
    p90_motion_px: float
    coherent_feature_ratio: float


@dataclass(frozen=True, slots=True)
class MotionReport:
    schema_version: int
    manifest_path: str
    source_sha256: str
    sampling_interval_ms: int
    frame_count: int
    eligible_pair_count: int
    analyzed_pair_count: int
    skipped_gap_pair_count: int
    unusable_pair_count: int
    median_motion_px_per_sample: float | None
    p90_motion_px_per_sample: float | None
    pairs: tuple[MotionPair, ...]
    limitations: tuple[str, ...]


def analyze_manifest_motion(
    manifest_path: str | Path,
    *,
    max_pairs: int = 300,
    cv2_module: Any | None = None,
) -> MotionReport:
    """Estimate sparse feature motion between adjacent sampled frames.

    Images are resized so the longest side is at most 640 px. Pairwise optical
    flow is reported in those resized-image pixels, not original screen pixels.
    To bound runtime, eligible pairs are sampled at a deterministic stride.
    """
    if isinstance(max_pairs, bool) or not isinstance(max_pairs, int) or max_pairs < 1:
        raise ValueError("max_pairs must be a positive integer")
    manifest_file = Path(manifest_path).expanduser().resolve()
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported sampling manifest schema version")
    fingerprint = payload.get("source_sha256")
    frames = payload.get("frames")
    interval = payload.get("interval_ms")
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        raise ValueError("Sampling manifest is missing its source fingerprint")
    if not isinstance(frames, list):
        raise ValueError("Sampling manifest has no frame list")
    if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
        raise ValueError("Sampling manifest must include a positive interval_ms")
    root = manifest_file.parent
    validated: list[tuple[int, Path]] = []
    for entry in frames:
        if (
            not isinstance(entry, dict)
            or isinstance(entry.get("timestamp_ms"), bool)
            or not isinstance(entry.get("timestamp_ms"), int)
            or entry["timestamp_ms"] < 0
            or not isinstance(entry.get("filename"), str)
            or not entry["filename"].strip()
            or Path(entry["filename"]).name != entry["filename"]
            or "/" in entry["filename"]
            or "\\" in entry["filename"]
        ):
            raise ValueError("Sampling manifest contains an invalid frame entry")
        validated.append((entry["timestamp_ms"], root / entry["filename"]))
    if any(right[0] <= left[0] for left, right in zip(validated, validated[1:])):
        raise ValueError("Sampling manifest timestamps must be strictly increasing")

    eligible = [
        (index, validated[index], validated[index + 1])
        for index in range(len(validated) - 1)
        if validated[index + 1][0] - validated[index][0] == interval
    ]
    gap_pairs = len(validated) - 1 - len(eligible)
    stride = max(1, math.ceil(len(eligible) / max_pairs))
    selected = eligible[::stride][:max_pairs]

    if cv2_module is None:
        try:
            import cv2 as cv2_module
        except ImportError as error:
            raise RuntimeError(
                "Motion analysis requires OpenCV. Install with: pip install -e .[vision]"
            ) from error

    results: list[MotionPair] = []
    unusable = 0
    for _index, (start_ms, first_path), (end_ms, second_path) in selected:
        first = cv2_module.imread(str(first_path), cv2_module.IMREAD_GRAYSCALE)
        second = cv2_module.imread(str(second_path), cv2_module.IMREAD_GRAYSCALE)
        if first is None or second is None:
            unusable += 1
            continue
        first = _resize_frame(cv2_module, first, max_dimension=640)
        second = _resize_frame(cv2_module, second, max_dimension=640)
        features = cv2_module.goodFeaturesToTrack(
            first, maxCorners=300, qualityLevel=0.01, minDistance=8, blockSize=7
        )
        if features is None or len(features) < 4:
            unusable += 1
            continue
        tracked, status, _error = cv2_module.calcOpticalFlowPyrLK(
            first, second, features, None
        )
        if tracked is None or status is None:
            unusable += 1
            continue
        old_points = features.reshape(-1, 2)
        new_points = tracked.reshape(-1, 2)
        valid = status.reshape(-1).astype(bool)
        if int(valid.sum()) < 4:
            unusable += 1
            continue
        dx = new_points[valid, 0] - old_points[valid, 0]
        dy = new_points[valid, 1] - old_points[valid, 1]
        magnitude = (dx * dx + dy * dy) ** 0.5
        # Fraction of tracked points whose displacement is within 3 resized-image
        # pixels of the median flow vector. This describes coherence, not aim.
        median_dx = float(_percentile(dx, 50))
        median_dy = float(_percentile(dy, 50))
        residual = ((dx - median_dx) ** 2 + (dy - median_dy) ** 2) ** 0.5
        coherent_ratio = float((residual <= 3.0).sum()) / len(residual)
        results.append(
            MotionPair(
                start_timestamp_ms=start_ms,
                end_timestamp_ms=end_ms,
                tracked_feature_count=int(valid.sum()),
                median_dx_px=round(float(_percentile(dx, 50)), 3),
                median_dy_px=round(float(_percentile(dy, 50)), 3),
                median_motion_px=round(float(_percentile(magnitude, 50)), 3),
                p90_motion_px=round(float(_percentile(magnitude, 90)), 3),
                coherent_feature_ratio=round(coherent_ratio, 3),
            )
        )

    magnitudes = [item.median_motion_px for item in results]
    limitations = (
        "Estimates visible feature movement between sampled images only.",
        "Pixels refer to resized images with longest side at most 640 px.",
        "Camera motion, recoil animation, moving objects, effects, compression, and scene changes can affect estimates.",
        "This does not measure mouse input, true aim direction, target alignment, hit probability, or player skill.",
        "Only adjacent frames exactly one sampling interval apart are eligible; timestamp gaps are excluded.",
        "Coherent-feature ratio is the share of tracked points within 3 resized-image pixels of the median flow vector; it is not a validated camera-motion classifier.",
        "When there are more eligible pairs than the configured limit, a deterministic stride subsamples them.",
    )
    return MotionReport(
        schema_version=1,
        manifest_path=str(manifest_file),
        source_sha256=fingerprint,
        sampling_interval_ms=interval,
        frame_count=len(validated),
        eligible_pair_count=len(eligible),
        analyzed_pair_count=len(results),
        skipped_gap_pair_count=gap_pairs,
        unusable_pair_count=unusable,
        median_motion_px_per_sample=(
            round(float(_percentile(magnitudes, 50)), 3) if magnitudes else None
        ),
        p90_motion_px_per_sample=(
            round(float(_percentile(magnitudes, 90)), 3) if magnitudes else None
        ),
        pairs=tuple(results),
        limitations=limitations,
    )


def write_motion_report(report: MotionReport, output_path: str | Path) -> Path:
    """Write a motion report as JSON without overwriting the input manifest."""
    target = Path(output_path).expanduser().resolve()
    if target == Path(report.manifest_path).expanduser().resolve():
        raise ValueError("Motion report cannot overwrite its source manifest")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def _resize_frame(cv2_module: Any, frame: Any, *, max_dimension: int) -> Any:
    height, width = frame.shape[:2]
    longest = max(height, width)
    if longest <= max_dimension:
        return frame
    scale = max_dimension / longest
    return cv2_module.resize(
        frame, (max(1, round(width * scale)), max(1, round(height * scale)))
    )


def _percentile(values: Any, percentile: float) -> float:
    """Linear-interpolated percentile without requiring NumPy in the public API."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Cannot calculate a percentile from an empty sequence")
    position = (len(ordered) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
