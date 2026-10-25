"""Tests for manually marked reticle/target coordinate storage and summaries."""
import json
from pathlib import Path

import pytest

from siegesense.vision.annotations import AnnotationStore, load_dataset
from siegesense.vision.spatial_analysis import summarize_spatial_error


def _manifest(path: Path) -> Path:
    result = path / "sampling_manifest.json"
    result.write_text(json.dumps({
        "schema_version": 1,
        "source_sha256": "coordinate-test-source",
        "frames": [
            {"timestamp_ms": 0, "filename": "frame0.png"},
            {"timestamp_ms": 100, "filename": "frame1.png"},
        ],
    }), encoding="utf-8")
    return result


def test_coordinate_points_round_trip_and_spatial_offsets(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    dataset_path = tmp_path / "annotations.json"
    store = AnnotationStore(manifest, dataset_path)
    store.add(
        0, "frame0.png", "crosshair_off_target", annotator="reviewer",
        reticle_x=0.5, reticle_y=0.5, target_x=0.6, target_y=0.4,
    )
    store.add(100, "frame1.png", "ambiguous", annotator="reviewer")
    reopened = AnnotationStore(manifest, dataset_path)
    dataset = load_dataset(dataset_path)

    assert dataset.annotations[0].reticle_x == 0.5
    assert dataset.annotations[0].target_y == 0.4
    assert dataset.annotations[1].reticle_x is None
    summary = summarize_spatial_error(dataset_path)
    assert summary.annotated_point_count == 1
    assert summary.excluded_without_both_points == 1
    assert summary.median_horizontal_offset_pct == 10.0
    assert summary.median_vertical_offset_pct == -10.0
    assert summary.median_distance_pct_frame_diagonal == pytest.approx(10.0)
    assert "not mouse input" in " ".join(summary.limitations)
    assert len(reopened.annotations) == 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"reticle_x": 0.5}, "require both x and y"),
        ({"reticle_x": -0.1, "reticle_y": 0.5}, "between 0 and 1"),
        ({"reticle_x": float("nan"), "reticle_y": 0.5}, "between 0 and 1"),
        ({"target_x": True, "target_y": 0.5}, "must be a number"),
    ],
)
def test_coordinate_validation_rejects_invalid_points(
    tmp_path: Path, kwargs: dict, message: str
) -> None:
    store = AnnotationStore(_manifest(tmp_path), tmp_path / "annotations.json")
    with pytest.raises(ValueError, match=message):
        store.add(0, "frame0.png", "ambiguous", annotator="reviewer", **kwargs)


def test_spatial_analysis_rejects_partial_coordinate_pairs(tmp_path: Path) -> None:
    dataset_path = tmp_path / "annotations.json"
    dataset_path.write_text(json.dumps({
        "schema_version": 1,
        "annotations": [{
            "annotation_id": "partial", "timestamp_ms": 0,
            "reticle_x": 0.5, "reticle_y": 0.5,
            "target_x": 0.6, "target_y": None,
        }],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="both reticle and target"):
        summarize_spatial_error(dataset_path)


def test_legacy_annotation_records_without_coordinates_remain_supported(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    dataset_path = tmp_path / "annotations.json"
    dataset_path.write_text(json.dumps({
        "schema_version": 1,
        "source_sha256": "coordinate-test-source",
        "manifest_path": str(manifest),
        "annotations": [{
            "annotation_id": "legacy", "timestamp_ms": 0,
            "frame_filename": "frame0.png", "label": "ambiguous",
            "note": "", "annotator": "reviewer", "created_at": "2026-01-01T00:00:00+00:00",
        }],
    }), encoding="utf-8")
    store = AnnotationStore(manifest, dataset_path)
    assert store.annotations[0].reticle_x is None
    summary = summarize_spatial_error(dataset_path)
    assert summary.annotated_point_count == 0
    assert summary.median_distance_pct_frame_diagonal is None
