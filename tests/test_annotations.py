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


def test_remove_persists_and_unknown_id_is_safe(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    dataset_path = tmp_path / "annotations.json"
    store = AnnotationStore(manifest, dataset_path)
    item = store.add(0, "frame_000000000ms.png", "unusable_frame", annotator="reviewer")
    assert store.remove(item.annotation_id)
    assert not store.remove("not-a-real-id")
    assert AnnotationStore(manifest, dataset_path).annotations == ()
