"""Tests for evaluation dataset hygiene and annotation coverage."""
import json
from pathlib import Path

import pytest

from siegesense.vision.evaluation import (
    compare_annotators,
    summarize_aim_frames,
    summarize_datasets,
    write_evaluation_report,
)
from siegesense.vision.report import main as report_main


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


def test_aim_frame_summary_is_descriptive_and_handles_no_crosshair_labels(
    tmp_path: Path,
) -> None:
    dataset = make_dataset(
        tmp_path / "aim.json",
        "source-a",
        ["crosshair_on_target", "crosshair_on_target", "crosshair_off_target",
         "target_transition", "ambiguous", "unusable_frame"],
    )
    summary = summarize_aim_frames(dataset)
    assert summary.crosshair_on_target_frames == 2
    assert summary.crosshair_off_target_frames == 1
    assert summary.determinate_crosshair_frames == 3
    assert summary.on_target_share_of_labelled_frames == pytest.approx(2 / 3)
    assert summary.target_transition_frames == 1
    assert summary.ambiguous_frames == 1
    assert summary.unusable_frames == 1

    no_crosshair = make_dataset(tmp_path / "empty-aim.json", "source-b", ["ambiguous"])
    assert summarize_aim_frames(no_crosshair).on_target_share_of_labelled_frames is None


def test_evaluation_rejects_duplicate_annotation_ids(tmp_path: Path) -> None:
    dataset = make_dataset(
        tmp_path / "duplicate-id.json", "source-a", ["ambiguous", "crosshair_on_target"]
    )
    payload = json.loads(dataset.read_text(encoding="utf-8"))
    payload["annotations"][1]["annotation_id"] = payload["annotations"][0]["annotation_id"]
    dataset.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate annotation ID"):
        summarize_datasets([("training", dataset)])


def test_evaluation_rejects_frame_path_traversal(tmp_path: Path) -> None:
    dataset = make_dataset(tmp_path / "unsafe-frame.json", "source-a", ["ambiguous"])
    payload = json.loads(dataset.read_text(encoding="utf-8"))
    payload["annotations"][0]["frame_filename"] = "../outside.png"
    dataset.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="local basename"):
        summarize_datasets([("training", dataset)])


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


def test_compare_annotators_rejects_duplicate_frame_labels(tmp_path: Path) -> None:
    first = make_dataset(
        tmp_path / "a.json", "same-source", ["ambiguous", "target_transition"]
    )
    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["annotations"][1]["timestamp_ms"] = payload["annotations"][0]["timestamp_ms"]
    payload["annotations"][1]["frame_filename"] = payload["annotations"][0]["frame_filename"]
    first.write_text(json.dumps(payload), encoding="utf-8")
    second = make_dataset(tmp_path / "b.json", "same-source", ["ambiguous"])
    with pytest.raises(ValueError, match="duplicate annotations"):
        compare_annotators(first, second)


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



def test_write_evaluation_report_includes_coverage_and_limitations(tmp_path: Path) -> None:
    dataset = make_dataset(
        tmp_path / "labels.json", "source-a",
        ["target_transition", "ambiguous"],
    )
    report_path = write_evaluation_report(
        tmp_path / "report.json", [("training", dataset)]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["model_performance_evaluated"] is False
    assert report["datasets"][0]["annotation_count"] == 2
    assert report["datasets"][0]["label_counts"]["crosshair_on_target"] == 0
    assert report["datasets"][0]["aim_frame_summary"]["on_target_share_of_labelled_frames"] is None
    assert report["limitations"]


def test_write_evaluation_report_does_not_overwrite_input(tmp_path: Path) -> None:
    dataset = make_dataset(tmp_path / "labels.json", "source-a", ["ambiguous"])
    original = dataset.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="must not overwrite"):
        write_evaluation_report(dataset, [("training", dataset)])
    assert dataset.read_text(encoding="utf-8") == original


def test_write_evaluation_report_includes_reviewer_agreement(tmp_path: Path) -> None:
    first = make_dataset(
        tmp_path / "a.json", "same-source",
        ["target_transition", "crosshair_on_target", "movement_start", "ambiguous"],
    )
    second = make_dataset(
        tmp_path / "b.json", "same-source",
        ["target_transition", "crosshair_on_target", "movement_stop", "ambiguous"],
    )
    report_path = write_evaluation_report(
        tmp_path / "report.json",
        [("training", first)],
        annotator_pairs=[("double-reviewed subset", first, second)],
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["annotator_agreement"][0]["overlapping_frames"] == 4
    assert report["annotator_agreement"][0]["exact_agreement"] == 3



def test_report_cli_writes_report_for_named_dataset(tmp_path: Path, capsys) -> None:
    dataset = make_dataset(tmp_path / "labels.json", "source-a", ["ambiguous"])
    output = tmp_path / "report.json"
    result = report_main([
        "--dataset", f"heldout={dataset}",
        "--output", str(output),
    ])
    captured = capsys.readouterr()
    assert result == 0
    assert output.is_file()
    assert "does not measure model performance" in captured.out
    assert json.loads(output.read_text(encoding="utf-8"))["datasets"][0]["dataset_name"] == "heldout"


def test_report_cli_includes_reviewer_pair(tmp_path: Path, capsys) -> None:
    first = make_dataset(
        tmp_path / "reviewer-a.json", "same-source",
        ["target_transition", "crosshair_on_target"],
    )
    second = make_dataset(
        tmp_path / "reviewer-b.json", "same-source",
        ["target_transition", "crosshair_off_target"],
    )
    output = tmp_path / "report.json"
    result = report_main([
        "--dataset", f"heldout={first}",
        "--agreement", f"double_review={first},{second}",
        "--output", str(output),
    ])
    assert result == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["annotator_agreement"][0]["name"] == "double_review"
    assert report["annotator_agreement"][0]["overlapping_frames"] == 2
    assert "Evaluation report written" in capsys.readouterr().out


def test_report_cli_requires_a_dataset(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        report_main(["--output", str(tmp_path / "report.json")])
    assert error.value.code == 2


def test_report_cli_returns_error_for_invalid_dataset(tmp_path: Path, capsys) -> None:
    result = report_main([
        "--dataset", f"missing={tmp_path / 'missing.json'}",
        "--output", str(tmp_path / "report.json"),
    ])
    assert result == 2
    assert "Evaluation report failed" in capsys.readouterr().err
