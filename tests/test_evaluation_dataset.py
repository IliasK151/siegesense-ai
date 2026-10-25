"""Tests for evaluation dataset hygiene and annotation coverage."""
import json
from pathlib import Path

import pytest

from siegesense.vision.evaluation import compare_annotators, summarize_datasets


def make_dataset(path: Path, source_hash: str, labels: list[str]) -> Path:
    path.write_text(json.dumps({
        "schema_version": 1,
        "source_sha256": source_hash,
        "manifest_path": "not-needed-for-summary.json",
        "annotations": [
            {
                "annotation_id": f"annotation-{index}",
                "timestamp_ms": index * 1000,
                "frame_filename": f"frame_{index}.png",
                "label": label,
                "note": "",
                "annotator": "reviewer",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
            for index, label in enumerate(labels)
        ],
    }), encoding="utf-8")
    return path


def test_summary_counts_labels_and_empty_categories(tmp_path: Path) -> None:
    dataset = make_dataset(
        tmp_path / "training.json", "source-a",
        ["target_transition", "target_transition", "ambiguous"],
    )
    (summary,) = summarize_datasets([("training", dataset)])
    assert summary.dataset_name == "training"
    assert summary.recording_count == 1
    assert summary.annotation_count == 3
    assert summary.label_counts["target_transition"] == 2
    assert summary.label_counts["ambiguous"] == 1
    assert summary.label_counts["movement_start"] == 0


def test_summary_rejects_same_recording_in_two_splits(tmp_path: Path) -> None:
    training = make_dataset(tmp_path / "training.json", "same-source", ["ambiguous"])
    evaluation = make_dataset(tmp_path / "evaluation.json", "same-source", ["crosshair_on_target"])
    with pytest.raises(ValueError, match="Recording leakage"):
        summarize_datasets([("training", training), ("evaluation", evaluation)])


def test_summary_allows_distinct_recordings(tmp_path: Path) -> None:
    training = make_dataset(tmp_path / "training.json", "source-a", ["ambiguous"])
    evaluation = make_dataset(tmp_path / "evaluation.json", "source-b", ["movement_start"])
    summaries = summarize_datasets([("training", training), ("evaluation", evaluation)])
    assert [summary.dataset_name for summary in summaries] == ["training", "evaluation"]


def test_summary_rejects_blank_dataset_name(tmp_path: Path) -> None:
    dataset = make_dataset(tmp_path / "data.json", "source-a", [])
    with pytest.raises(ValueError, match="name cannot be empty"):
        summarize_datasets([(" ", dataset)])


def test_compare_annotators_reports_exact_agreement_and_kappa(tmp_path: Path) -> None:
    first = make_dataset(
        tmp_path / "reviewer-a.json", "same-source",
        ["target_transition", "crosshair_on_target", "movement_start", "ambiguous"],
    )
    second = make_dataset(
        tmp_path / "reviewer-b.json", "same-source",
        ["target_transition", "crosshair_on_target", "movement_stop", "ambiguous"],
    )
    report = compare_annotators(first, second)
    assert report.overlapping_frames == 4
    assert report.exact_agreement == 3
    assert report.observed_agreement == pytest.approx(0.75)
    assert report.cohens_kappa is not None
    assert report.cohens_kappa < 1.0


def test_compare_annotators_rejects_different_recordings(tmp_path: Path) -> None:
    first = make_dataset(tmp_path / "a.json", "source-a", ["ambiguous"])
    second = make_dataset(tmp_path / "b.json", "source-b", ["ambiguous"])
    with pytest.raises(ValueError, match="same source recording"):
        compare_annotators(first, second)


def test_compare_annotators_rejects_no_overlapping_frames(tmp_path: Path) -> None:
    first = make_dataset(tmp_path / "a.json", "same-source", ["ambiguous"])
    second = make_dataset(tmp_path / "b.json", "same-source", [])
    with pytest.raises(ValueError, match="no overlapping"):
        compare_annotators(first, second)
