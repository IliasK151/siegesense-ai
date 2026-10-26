"""Temporal summaries of manually marked target-relative offsets.

This module counts offset sign changes only for consecutive sampled frames that share
an explicit human-assigned target track ID. It does not infer overshoot or which object
caused the change.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from siegesense.vision.annotations import load_dataset


@dataclass(frozen=True, slots=True)
class OffsetSignChange:
    target_track_id: str
    axis: str
    before_timestamp_ms: int
    after_timestamp_ms: int
    before_offset_pct_axis: float
    after_offset_pct_axis: float
    sign_change: str


@dataclass(frozen=True, slots=True)
class AimTransitionSummary:
    sampling_interval_ms: int | None
    unique_target_track_count: int
    tracked_point_count: int
    eligible_adjacent_pair_count: int
    timestamp_gap_count: int
    excluded_without_track_id_count: int
    excluded_without_point_pairs_count: int
    horizontal_sign_change_count: int
    vertical_sign_change_count: int
    sign_changes: tuple[OffsetSignChange, ...]
    limitations: tuple[str, ...]


def summarize_aim_transitions(
    dataset_path: str | Path,
    *,
    sampling_interval_ms: int | None = None,
) -> AimTransitionSummary:
    """Summarize manually marked target-relative offset sign changes.

    Positive horizontal offset means the target point is right of the reticle point;
    positive vertical offset means the target point is below it. Offsets are percentages
    of frame width or frame height, respectively. A sign change is only counted between
    same-track annotations whose timestamps differ by exactly one known sample interval.
    """
    # Validate an explicit interval before opening the annotation dataset. This
    # keeps argument validation deterministic even when dataset_path is missing.
    if sampling_interval_ms is not None:
        _validate_sampling_interval(sampling_interval_ms)

    dataset_file = Path(dataset_path).expanduser().resolve()
    dataset = load_dataset(dataset_file)
    interval = _resolve_sampling_interval(
        dataset.manifest_path, sampling_interval_ms=sampling_interval_ms
    )

    grouped: dict[str, list[tuple[int, float, float]]] = {}
    excluded_without_track_id = 0
    excluded_without_points = 0
    tracked_points = 0
    for annotation in dataset.annotations:
        raw_track_id = annotation.target_track_id
        if not isinstance(raw_track_id, str) or not raw_track_id.strip():
            excluded_without_track_id += 1
            continue
        if (
            annotation.reticle_x is None
            or annotation.reticle_y is None
            or annotation.target_x is None
            or annotation.target_y is None
        ):
            excluded_without_points += 1
            continue

        track_id = raw_track_id.strip().casefold()
        dx_pct = (annotation.target_x - annotation.reticle_x) * 100
        dy_pct = (annotation.target_y - annotation.reticle_y) * 100
        grouped.setdefault(track_id, []).append(
            (annotation.timestamp_ms, dx_pct, dy_pct)
        )
        tracked_points += 1

    sign_changes: list[OffsetSignChange] = []
    eligible_pairs = 0
    timestamp_gaps = 0
    for track_id, samples in sorted(grouped.items()):
        samples.sort(key=lambda item: item[0])
        timestamps = [item[0] for item in samples]
        if len(timestamps) != len(set(timestamps)):
            raise ValueError(
                f"Target track {track_id!r} has duplicate timestamps; "
                "review duplicate annotations before analysis"
            )
        for before, after in zip(samples, samples[1:]):
            delta_ms = after[0] - before[0]
            if interval is None:
                continue
            if delta_ms != interval:
                timestamp_gaps += 1
                continue
            eligible_pairs += 1
            _record_sign_change(
                sign_changes,
                track_id=track_id,
                axis="horizontal",
                before_timestamp_ms=before[0],
                after_timestamp_ms=after[0],
                before_offset_pct=before[1],
                after_offset_pct=after[1],
            )
            _record_sign_change(
                sign_changes,
                track_id=track_id,
                axis="vertical",
                before_timestamp_ms=before[0],
                after_timestamp_ms=after[0],
                before_offset_pct=before[2],
                after_offset_pct=after[2],
            )

    horizontal_count = sum(item.axis == "horizontal" for item in sign_changes)
    vertical_count = sum(item.axis == "vertical" for item in sign_changes)
    limitations = [
        "Reticle points, target points, and target track IDs are manually supplied.",
        "A sign change means the target-relative offset changed sides between sampled frames; "
        "it does not identify which object moved.",
        "A sign change alone is not proof of overshoot, correction, a hit or miss, or a "
        "sensitivity problem.",
        "Only same-track point pairs exactly one sampling interval apart are compared. "
        "Missing points and timestamp gaps break the sequence.",
        "Offsets are percentages of frame width (horizontal) or frame height (vertical); "
        "they are not mouse input or world-space angles.",
        "No automatic reticle/opponent detection or model-performance evaluation is used.",
    ]
    if interval is None:
        limitations.append(
            "The sampling interval is unknown; temporal sign changes are not calculated."
        )

    return AimTransitionSummary(
        sampling_interval_ms=interval,
        unique_target_track_count=len(grouped),
        tracked_point_count=tracked_points,
        eligible_adjacent_pair_count=eligible_pairs,
        timestamp_gap_count=timestamp_gaps,
        excluded_without_track_id_count=excluded_without_track_id,
        excluded_without_point_pairs_count=excluded_without_points,
        horizontal_sign_change_count=horizontal_count,
        vertical_sign_change_count=vertical_count,
        sign_changes=tuple(sign_changes),
        limitations=tuple(limitations),
    )


def write_aim_transition_report(
    dataset_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Export manually marked target-relative offset changes as a local JSON report.

    The report cannot overwrite the annotation dataset, its sampling manifest, the
    source recording, or a sampled frame referenced by that manifest.
    """
    source = Path(dataset_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    dataset = load_dataset(source)
    manifest_path = Path(dataset.manifest_path).expanduser().resolve()

    protected_paths = {source, manifest_path}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    if not isinstance(manifest, dict):
        manifest = {}

    source_path = manifest.get("source_path")
    if isinstance(source_path, str) and source_path.strip():
        media_path = Path(source_path).expanduser()
        if not media_path.is_absolute():
            media_path = manifest_path.parent / media_path
        protected_paths.add(media_path.resolve())

    frames = manifest.get("frames", [])
    if isinstance(frames, list):
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            filename = frame.get("filename")
            if (
                isinstance(filename, str)
                and filename.strip()
                and Path(filename).name == filename
                and "/" not in filename
                and "\\" not in filename
            ):
                protected_paths.add((manifest_path.parent / filename).resolve())

    if output in protected_paths:
        raise ValueError(
            "Aim-transition report output must not overwrite the source recording, "
            "sampling manifest, annotation dataset, or sampled frame"
        )

    summary = summarize_aim_transitions(source)
    report = {
        "schema_version": 1,
        "report_type": "manual_target_relative_offset_sign_changes",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(source),
        "source_sha256": dataset.source_sha256,
        "summary": {
            "sampling_interval_ms": summary.sampling_interval_ms,
            "unique_target_track_count": summary.unique_target_track_count,
            "tracked_point_count": summary.tracked_point_count,
            "eligible_adjacent_pair_count": summary.eligible_adjacent_pair_count,
            "timestamp_gap_count": summary.timestamp_gap_count,
            "excluded_without_track_id_count": summary.excluded_without_track_id_count,
            "excluded_without_point_pairs_count": summary.excluded_without_point_pairs_count,
            "horizontal_sign_change_count": summary.horizontal_sign_change_count,
            "vertical_sign_change_count": summary.vertical_sign_change_count,
        },
        "sign_changes": [asdict(item) for item in summary.sign_changes],
        "limitations": list(summary.limitations),
        "automatic_detection_used": False,
        "overshoot_diagnosed": False,
        "aim_accuracy_evaluated": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temporary.replace(output)
    return output


def _validate_sampling_interval(sampling_interval_ms: int) -> int:
    """Validate and return an explicitly supplied sampling interval."""
    if (
        isinstance(sampling_interval_ms, bool)
        or not isinstance(sampling_interval_ms, int)
        or sampling_interval_ms <= 0
    ):
        raise ValueError("Sampling interval must be a positive integer number of milliseconds")
    return sampling_interval_ms


def _resolve_sampling_interval(
    manifest_path: str,
    *,
    sampling_interval_ms: int | None,
) -> int | None:
    if sampling_interval_ms is not None:
        return _validate_sampling_interval(sampling_interval_ms)

    try:
        manifest = json.loads(
            Path(manifest_path).expanduser().read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    candidate = manifest.get("interval_ms")
    if (
        isinstance(candidate, int)
        and not isinstance(candidate, bool)
        and candidate > 0
    ):
        return candidate
    return None


def _record_sign_change(
    output: list[OffsetSignChange],
    *,
    track_id: str,
    axis: str,
    before_timestamp_ms: int,
    after_timestamp_ms: int,
    before_offset_pct: float,
    after_offset_pct: float,
) -> None:
    if not (
        (before_offset_pct < 0 < after_offset_pct)
        or (after_offset_pct < 0 < before_offset_pct)
    ):
        return
    direction = (
        "negative_to_positive"
        if before_offset_pct < 0 < after_offset_pct
        else "positive_to_negative"
    )
    output.append(
        OffsetSignChange(
            target_track_id=track_id,
            axis=axis,
            before_timestamp_ms=before_timestamp_ms,
            after_timestamp_ms=after_timestamp_ms,
            before_offset_pct_axis=round(before_offset_pct, 4),
            after_offset_pct_axis=round(after_offset_pct, 4),
            sign_change=direction,
        )
    )
