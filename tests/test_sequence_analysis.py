"""Tests for human-labelled temporal sequence summaries."""
import json
from pathlib import Path

import pytest

from siegesense.vision.sequence_analysis import summarize_annotated_sequences


def make_dataset(path: Path, labels: list[tuple[int, str]], manifest_path: str = "missing.json") -> Path:
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "source_sha256": "source-fingerprint",
            "manifest_path": manifest_path,
            "annotations": [
                {
                    "annotation_id": f"annotation-{index}",
                    "timestamp_ms": timestamp,
                    "frame_filename": f"frame_{timestamp}.png",
                    "label": label,
                    "note": "",
                    "annotator": "reviewer",
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
                for index, (timestamp, label) in enumerate(labels)
            ],
        }),
        encoding="utf-8",
    )
    return path


def test_sequence_summary_measures_only_contiguous_labelled_runs(tmp_path: Path) -> None:
    dataset = make_dataset(
        tmp_path / "labels.json",
        [
            (0, "crosshair_off_target"),
            (100, "crosshair_off_target"),
            (200, "crosshair_on_target"),
            (300, "crosshair_off_target"),
            (400, "crosshair_off_target"),
            (600, "crosshair_off_target"),
            (700, "movement_start"),
            (800, "movement_stop"),
        ],
    )
    summary = summarize_annotated_sequences(dataset, sampling_interval_ms=100)
    assert summary.annotated_frame_count == 8
    assert summary.timestamp_gap_count == 1
    assert summary.off_target_runs.run_count == 3
    assert summary.off_target_runs.total_frames_in_runs == 5
    assert summary.off_target_runs.median_observed_span_ms == 100
    assert summary.off_target_runs.longest_observed_span_ms == 100
    assert summary.on_target_runs.run_count == 1
    assert summary.on_target_runs.longest_observed_span_ms == 0
    assert summary.movement_start_count == 1
    assert summary.movement_stop_count == 1
    assert summary.off_to_on_transitions == 1
    assert summary.on_to_off_transitions == 1
    assert any("not precise event duration" in item for item in summary.limitations)


def test_sequence_summary_without_interval_does_not_invent_timing(tmp_path: Path) -> None:
    dataset = make_dataset(
        tmp_path / "labels.json",
        [(0, "crosshair_off_target"), (100, "crosshair_off_target")],
    )
    summary = summarize_annotated_sequences(dataset)
    assert summary.sampling_interval_ms is None
    assert summary.off_target_runs.run_count is None
    assert summary.off_target_runs.median_observed_span_ms is None
    assert summary.off_target_runs.longest_observed_span_ms is None
    assert summary.off_to_on_transitions is None
    assert summary.on_to_off_transitions is None
    assert any("timing is unavailable" in item for item in summary.limitations)


def test_sequence_summary_reads_interval_from_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "sampling_manifest.json"
    manifest.write_text(json.dumps({"interval_ms": 250}), encoding="utf-8")
    dataset = make_dataset(
        tmp_path / "labels.json",
        [(0, "crosshair_off_target"), (250, "crosshair_off_target")],
        str(manifest),
    )
    summary = summarize_annotated_sequences(dataset)
    assert summary.sampling_interval_ms == 250
    assert summary.off_target_runs.longest_observed_span_ms == 250


def test_sequence_summary_rejects_invalid_interval_and_duplicate_timestamps(
    tmp_path: Path,
) -> None:
    dataset = make_dataset(
        tmp_path / "labels.json",
        [(0, "crosshair_off_target"), (100, "crosshair_on_target")],
    )
    with pytest.raises(ValueError, match="positive integer"):
        summarize_annotated_sequences(dataset, sampling_interval_ms=0)
    duplicate = make_dataset(
        tmp_path / "duplicate.json",
        [(0, "crosshair_off_target"), (0, "crosshair_on_target")],
    )
    with pytest.raises(ValueError, match="unique annotation timestamps"):
        summarize_annotated_sequences(duplicate, sampling_interval_ms=100)



def test_sequence_transition_counts_do_not_bridge_timestamp_gaps(tmp_path: Path) -> None:
    dataset = make_dataset(
        tmp_path / "gap-transitions.json",
        [
            (0, "crosshair_off_target"),
            (200, "crosshair_on_target"),
            (300, "crosshair_off_target"),
        ],
    )

    summary = summarize_annotated_sequences(dataset, sampling_interval_ms=100)

    assert summary.off_to_on_transitions == 0
    assert summary.on_to_off_transitions == 1
