"""Tests for local human annotations of sampled frames."""
import json
from pathlib import Path

import pytest

from siegesense.vision.annotations import AnnotationStore, load_dataset


def make_manifest(path: Path, *, fingerprint: str = "abc123") -> Path:
    manifest = path / "sampling_manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "source_sha256": fingerprint,
        "frames": [
            {"timestamp_ms": 0, "filename": "frame_000000000ms.png"},
            {"timestamp_ms": 1000, "filename": "frame_000001000ms.png"},
        ],
    }), encoding="utf-8")
    return manifest


def test_annotations_round_trip_and_are_sorted(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    store = AnnotationStore(manifest, tmp_path / "annotations.json")
    later = store.add(1000, "frame_000001000ms.png", "crosshair_off_target",
                      annotator="reviewer", note="overshot after target switch")
    earlier = store.add(0, "frame_000000000ms.png", "target_transition",
                        annotator="reviewer")
    reopened = AnnotationStore(manifest, tmp_path / "annotations.json")
    assert [item.timestamp_ms for item in reopened.annotations] == [0, 1000]
    dataset = load_dataset(tmp_path / "annotations.json")
    assert dataset.source_sha256 == "abc123"
    assert dataset.annotations[1].annotation_id == later.annotation_id
    assert dataset.annotations[0].annotation_id == earlier.annotation_id
    assert "overshot after target switch" == dataset.annotations[1].note


@pytest.mark.parametrize(
    ("timestamp_ms", "filename", "label", "annotator", "message"),
    [
        (10, "missing.png", "ambiguous", "reviewer", "reference a frame"),
        (0, "frame_000000000ms.png", "made_up_label", "reviewer", "Unsupported annotation label"),
        (-1, "frame_000000000ms.png", "ambiguous", "reviewer", "zero or greater"),
        (0, "frame_000000000ms.png", "ambiguous", " ", "cannot be empty"),
    ],
)
def test_invalid_annotations_are_rejected(
    tmp_path: Path, timestamp_ms: int, filename: str, label: str,
    annotator: str, message: str,
) -> None:
    manifest = make_manifest(tmp_path)
    store = AnnotationStore(manifest, tmp_path / "annotations.json")
    with pytest.raises(ValueError, match=message):
        store.add(timestamp_ms, filename, label, annotator=annotator)


def test_annotations_cannot_be_loaded_for_a_different_recording(tmp_path: Path) -> None:
    first_manifest = make_manifest(tmp_path, fingerprint="first")
    store = AnnotationStore(first_manifest, tmp_path / "annotations.json")
    store.add(0, "frame_000000000ms.png", "ambiguous", annotator="reviewer")
    second_manifest = make_manifest(tmp_path, fingerprint="second")
    with pytest.raises(ValueError, match="different source recording"):
        AnnotationStore(second_manifest, tmp_path / "annotations.json")


def test_update_changes_label_and_note_without_changing_frame(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    dataset_path = tmp_path / "annotations.json"
    store = AnnotationStore(manifest, dataset_path)
    original = store.add(
        0, "frame_000000000ms.png", "ambiguous",
        annotator="reviewer", note="initial note",
    )
    updated = store.update(
        original.annotation_id,
        label="crosshair_on_target",
        annotator="reviewer 2",
        note="corrected after replay",
    )
    reopened = AnnotationStore(manifest, dataset_path)
    assert updated.annotation_id == original.annotation_id
    assert updated.timestamp_ms == original.timestamp_ms
    assert updated.frame_filename == original.frame_filename
    assert updated.label == "crosshair_on_target"
    assert updated.annotator == "reviewer 2"
    assert updated.note == "corrected after replay"
    assert reopened.annotations == (updated,)


def test_update_rejects_unknown_id_and_invalid_label(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    store = AnnotationStore(manifest, tmp_path / "annotations.json")
    with pytest.raises(ValueError, match="does not exist"):
        store.update("unknown", label="ambiguous", annotator="reviewer")
    item = store.add(0, "frame_000000000ms.png", "ambiguous", annotator="reviewer")
    with pytest.raises(ValueError, match="Unsupported annotation label"):
        store.update(item.annotation_id, label="not-a-label", annotator="reviewer")


def test_remove_persists_and_unknown_id_is_safe(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    dataset_path = tmp_path / "annotations.json"
    store = AnnotationStore(manifest, dataset_path)
    item = store.add(0, "frame_000000000ms.png", "unusable_frame", annotator="reviewer")
    assert store.remove(item.annotation_id)
    assert not store.remove("not-a-real-id")
    assert AnnotationStore(manifest, dataset_path).annotations == ()



def test_update_preserves_spatial_points_unless_replaced_explicitly(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    dataset_path = tmp_path / "annotations.json"
    store = AnnotationStore(manifest, dataset_path)
    original = store.add(
        0, "frame_000000000ms.png", "crosshair_off_target",
        annotator="reviewer",
        reticle_x=0.5, reticle_y=0.5, target_x=0.7, target_y=0.4,
    )

    edited = store.update(
        original.annotation_id,
        label="ambiguous",
        annotator="reviewer 2",
        note="label changed, coordinates should remain",
    )
    assert (edited.reticle_x, edited.reticle_y, edited.target_x, edited.target_y) == (
        0.5, 0.5, 0.7, 0.4
    )

    cleared = store.update(
        original.annotation_id,
        label="ambiguous",
        annotator="reviewer 2",
        note="cleared points",
        reticle_x=None, reticle_y=None, target_x=None, target_y=None,
    )
    assert (cleared.reticle_x, cleared.reticle_y, cleared.target_x, cleared.target_y) == (
        None, None, None, None
    )
    assert AnnotationStore(manifest, dataset_path).annotations == (cleared,)


def test_update_rejects_partial_coordinate_argument_sets(tmp_path: Path) -> None:
    store = AnnotationStore(make_manifest(tmp_path), tmp_path / "annotations.json")
    item = store.add(0, "frame_000000000ms.png", "ambiguous", annotator="reviewer")
    with pytest.raises(ValueError, match="all four spatial coordinate fields"):
        store.update(
            item.annotation_id,
            label=item.label,
            annotator=item.annotator,
            reticle_x=0.5,
            reticle_y=0.5,
        )


def test_target_track_id_is_normalized_and_preserved_during_edits(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    dataset_path = tmp_path / "annotations.json"
    store = AnnotationStore(manifest, dataset_path)
    original = store.add(
        0,
        "frame_000000000ms.png",
        "crosshair_off_target",
        annotator="reviewer",
        target_track_id="  Target-A  ",
    )

    edited = store.update(
        original.annotation_id,
        label="crosshair_on_target",
        annotator="reviewer",
        note="label reviewed",
    )
    assert original.target_track_id == "target-a"
    assert edited.target_track_id == "target-a"

    cleared = store.update(
        original.annotation_id,
        label="crosshair_on_target",
        annotator="reviewer",
        note="clear grouping",
        target_track_id="   ",
    )
    assert cleared.target_track_id is None


def test_legacy_annotation_json_without_target_track_id_still_loads(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    dataset_path = tmp_path / "legacy-annotations.json"
    dataset_path.write_text(
        json.dumps({
            "schema_version": 1,
            "source_sha256": "abc123",
            "manifest_path": str(manifest),
            "annotations": [{
                "annotation_id": "legacy-note",
                "timestamp_ms": 0,
                "frame_filename": "frame_000000000ms.png",
                "label": "ambiguous",
                "note": "old record",
                "annotator": "reviewer",
                "created_at": "2026-01-01T00:00:00+00:00",
            }],
        }),
        encoding="utf-8",
    )

    dataset = load_dataset(dataset_path)

    assert len(dataset.annotations) == 1
    assert dataset.annotations[0].target_track_id is None

