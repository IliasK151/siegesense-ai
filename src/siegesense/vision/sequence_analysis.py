"""Temporal summaries of consecutive human-labelled gameplay frames.

These are sampled-frame observations, not automatic aim detection or skill scores.
Only runs with known sampling intervals and adjacent annotated samples are timed.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from siegesense.vision.annotations import load_dataset


@dataclass(frozen=True, slots=True)
class LabelRunSummary:
    label: str
    run_count: int | None
    total_frames_in_runs: int
    median_observed_span_ms: float | None
    longest_observed_span_ms: int | None


@dataclass(frozen=True, slots=True)
class SequenceSummary:
    sampling_interval_ms: int | None
    annotated_frame_count: int
    timestamp_gap_count: int
    off_target_runs: LabelRunSummary
    on_target_runs: LabelRunSummary
    movement_start_count: int
    movement_stop_count: int
    off_to_on_transitions: int | None
    on_to_off_transitions: int | None
    limitations: tuple[str, ...]


def summarize_annotated_sequences(
    dataset_path: str | Path,
    *,
    sampling_interval_ms: int | None = None,
) -> SequenceSummary:
    """Summarize contiguous annotated runs using a known sample interval.

    A run's observed span is the distance from its first to last sampled frame,
    not a precise event duration. Runs break on a different label or a missing
    sample interval. Sparse annotations are not interpolated.
    """
    dataset = load_dataset(dataset_path)
    if sampling_interval_ms is None:
        manifest_path = Path(dataset.manifest_path).expanduser()
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                candidate = manifest.get("interval_ms")
                if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate > 0:
                    sampling_interval_ms = candidate
            except (OSError, json.JSONDecodeError):
                sampling_interval_ms = None
    if sampling_interval_ms is not None and (
        isinstance(sampling_interval_ms, bool)
        or not isinstance(sampling_interval_ms, int)
        or sampling_interval_ms <= 0
    ):
        raise ValueError("Sampling interval must be a positive integer number of milliseconds")

    annotations = sorted(dataset.annotations, key=lambda item: (item.timestamp_ms, item.frame_filename))
    if len({item.timestamp_ms for item in annotations}) != len(annotations):
        # Different frames should not share timestamps in one sampled manifest.
        raise ValueError("Sequence analysis requires unique annotation timestamps")

    def collect_runs(target_label: str) -> LabelRunSummary:
        runs: list[list[int]] = []
        current: list[int] = []
        previous_timestamp: int | None = None
        for item in annotations:
            is_adjacent = (
                previous_timestamp is not None
                and sampling_interval_ms is not None
                and item.timestamp_ms - previous_timestamp == sampling_interval_ms
            )
            if item.label == target_label:
                if current and is_adjacent:
                    current.append(item.timestamp_ms)
                else:
                    if current:
                        runs.append(current)
                    current = [item.timestamp_ms]
            else:
                if current:
                    runs.append(current)
                    current = []
            previous_timestamp = item.timestamp_ms
        if current:
            runs.append(current)
        spans = (
            [(run[-1] - run[0]) if len(run) > 1 else 0 for run in runs]
            if sampling_interval_ms is not None
            else None
        )
        return LabelRunSummary(
            label=target_label,
            run_count=len(runs) if sampling_interval_ms is not None else None,
            total_frames_in_runs=sum(len(run) for run in runs),
            median_observed_span_ms=(
                statistics.median(spans) if spans else None
            ) if spans is not None else None,
            longest_observed_span_ms=max(spans) if spans else None,
        )

    gap_count = 0
    if sampling_interval_ms is not None:
        gap_count = sum(
            current.timestamp_ms - previous.timestamp_ms != sampling_interval_ms
            for previous, current in zip(annotations, annotations[1:])
        )

    off_to_on_transitions = None
    on_to_off_transitions = None
    if sampling_interval_ms is not None:
        adjacent_pairs = (
            (previous.label, current.label)
            for previous, current in zip(annotations, annotations[1:])
            if current.timestamp_ms - previous.timestamp_ms == sampling_interval_ms
        )
        transitions = list(adjacent_pairs)
        off_to_on_transitions = sum(
            first == "crosshair_off_target" and second == "crosshair_on_target"
            for first, second in transitions
        )
        on_to_off_transitions = sum(
            first == "crosshair_on_target" and second == "crosshair_off_target"
            for first, second in transitions
        )

    limitations = [
        "Labels are human annotations, not automatic predictions.",
        "Observed span runs from first to last sampled frame; it is not precise event duration.",
        "Unlabelled frames are not inferred, and gaps break runs.",
        "Results describe only the frames selected and annotated by the reviewer.",
    ]
    if sampling_interval_ms is None:
        limitations.append(
            "Sampling interval is unknown; contiguous run timing is unavailable."
        )
    return SequenceSummary(
        sampling_interval_ms=sampling_interval_ms,
        annotated_frame_count=len(annotations),
        timestamp_gap_count=gap_count,
        off_target_runs=collect_runs("crosshair_off_target"),
        on_target_runs=collect_runs("crosshair_on_target"),
        movement_start_count=sum(item.label == "movement_start" for item in annotations),
        movement_stop_count=sum(item.label == "movement_stop" for item in annotations),
        off_to_on_transitions=off_to_on_transitions,
        on_to_off_transitions=on_to_off_transitions,
        limitations=tuple(limitations),
    )
