"""Tests for manually marked target-relative temporal analysis."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from siegesense.vision.aim_transition_analysis import (
    summarize_aim_transitions,
    write_aim_transition_report,
)
from siegesense.vision.annotations import AnnotationStore


def make_manifest(
    root: Path,
    *,
    times: tuple[int, ...] = (0, 1000, 2000, 3000),
    source_path: str | None = None,
) -> Path:
    manifest_path = root / "sampling_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_path": source_path,
                "source_sha256": "clip-fingerprint",
                "interval_ms": 1000,
                "frames": [
                    {"timestamp_ms": timestamp, "filename": f"frame_{timestamp}.png"}
                    for timestamp in times
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def add_point(
    store: AnnotationStore,
    timestamp_ms: int,
    *,
    track_id: str,
    reticle_x: float,
    target_x: float,
    reticle_y: float = 0.5,
    target_y: float = 0.5,
) -> None:
    store.add(
        timestamp_ms,
        f"frame_{timestamp_ms}.png",
        "crosshair_off_target",
        annotator="reviewer",
        target_track_id=track_id,
        reticle_x=reticle_x,
        reticle_y=reticle_y,
        target_x=target_x,
        target_y=target_y,
    )


def test_reports_same_track_horizontal_sign_change(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    store = AnnotationStore(manifest, tmp_path / "annotations.json")
    add_point(store, 0, track_id="Target-A", reticle_x=0.7, target_x=0.3)
    add_point(store, 1000, track_id="target-a", reticle_x=0.3, target_x=0.7)
    add_point(store, 2000, track_id="target-a", reticle_x=0.2, target_x=0.7)

    summary = summarize_aim_transitions(tmp_path / "annotations.json")

    assert summary.unique_target_track_count == 1
    assert summary.tracked_point_count == 3
    assert summary.eligible_adjacent_pair_count == 2
    assert summary.horizontal_sign_change_count == 1
    assert summary.vertical_sign_change_count == 0
    assert summary.sign_changes[0].target_track_id == "target-a"
    assert summary.sign_changes[0].axis == "horizontal"
    assert summary.sign_changes[0].before_offset_pct_axis == -40.0
    assert summary.sign_changes[0].after_offset_pct_axis == 40.0
    assert "not proof of overshoot" in " ".join(summary.limitations)


def test_different_tracks_and_timestamp_gaps_are_not_joined(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path, times=(0, 1000, 3000))
    store = AnnotationStore(manifest, tmp_path / "annotations.json")
    add_point(store, 0, track_id="target-a", reticle_x=0.7, target_x=0.3)
    add_point(store, 1000, track_id="target-b", reticle_x=0.3, target_x=0.7)
    add_point(store, 3000, track_id="target-a", reticle_x=0.3, target_x=0.7)

    summary = summarize_aim_transitions(tmp_path / "annotations.json")

    assert summary.unique_target_track_count == 2
    assert summary.eligible_adjacent_pair_count == 0
    assert summary.timestamp_gap_count == 1
    assert summary.horizontal_sign_change_count == 0


def test_missing_track_or_points_are_reported_as_excluded(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    store = AnnotationStore(manifest, tmp_path / "annotations.json")
    store.add(
        0, "frame_0.png", "ambiguous", annotator="reviewer",
        reticle_x=0.5, reticle_y=0.5, target_x=0.4, target_y=0.5,
    )
    store.add(
        1000, "frame_1000.png", "ambiguous", annotator="reviewer",
        target_track_id="target-a",
    )

    summary = summarize_aim_transitions(tmp_path / "annotations.json")

    assert summary.excluded_without_track_id_count == 1
    assert summary.excluded_without_point_pairs_count == 1
    assert summary.tracked_point_count == 0
    assert summary.horizontal_sign_change_count == 0


def test_interval_must_be_positive_when_supplied(tmp_path: Path) -> None:
    make_manifest(tmp_path)
    store = AnnotationStore(tmp_path / "sampling_manifest.json", tmp_path / "annotations.json")
    with pytest.raises(ValueError, match="positive integer"):
        summarize_aim_transitions(
            tmp_path / "annotations.json",
            sampling_interval_ms=0,
        )


def test_report_export_is_explicit_and_protects_source_data(tmp_path: Path) -> None:
    source_media = tmp_path / "recording.mp4"
    source_media.write_bytes(b"sample clip")
    manifest = make_manifest(tmp_path, source_path=str(source_media))
    store = AnnotationStore(manifest, tmp_path / "annotations.json")
    add_point(store, 0, track_id="target-a", reticle_x=0.7, target_x=0.3)
    add_point(store, 1000, track_id="target-a", reticle_x=0.3, target_x=0.7)
    dataset_path = tmp_path / "annotations.json"
    before = dataset_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="must not overwrite"):
        write_aim_transition_report(dataset_path, dataset_path)
    with pytest.raises(ValueError, match="must not overwrite"):
        write_aim_transition_report(dataset_path, source_media)

    output = write_aim_transition_report(dataset_path, tmp_path / "transition-report.json")
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["report_type"] == "manual_target_relative_offset_sign_changes"
    assert report["summary"]["horizontal_sign_change_count"] == 1
    assert report["automatic_detection_used"] is False
    assert report["overshoot_diagnosed"] is False
    assert report["aim_accuracy_evaluated"] is False
    assert dataset_path.read_text(encoding="utf-8") == before


def test_missing_sampling_interval_does_not_infer_crossings(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload.pop("interval_ms")
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    store = AnnotationStore(manifest, tmp_path / "annotations.json")
    add_point(store, 0, track_id="target-a", reticle_x=0.7, target_x=0.3)
    add_point(store, 1000, track_id="target-a", reticle_x=0.3, target_x=0.7)

    summary = summarize_aim_transitions(tmp_path / "annotations.json")

    assert summary.sampling_interval_ms is None
    assert summary.eligible_adjacent_pair_count == 0
    assert summary.horizontal_sign_change_count == 0
    assert any("interval is unknown" in item for item in summary.limitations)
