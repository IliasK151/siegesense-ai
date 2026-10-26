"""Integration coverage for manually grouped temporal aim-transition review."""

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_ui_saves_same_target_points_and_exports_transition_report(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frames_dir = tmp_path / "sampled"
    frames_dir.mkdir()
    frame_names = ("frame_000000000ms.png", "frame_000001000ms.png")
    for filename in frame_names:
        pixmap = QPixmap(320, 180)
        pixmap.fill(Qt.GlobalColor.darkBlue)
        assert pixmap.save(str(frames_dir / filename))

    recording = tmp_path / "recording.mp4"
    recording.write_bytes(b"local test fixture")
    manifest_path = frames_dir / "sampling_manifest.json"
    manifest_path.write_text(
        json.dumps({
            "schema_version": 1,
            "source_path": str(recording),
            "source_sha256": "transition-ui-test",
            "source_fps": 30.0,
            "source_width": 320,
            "source_height": 180,
            "duration_ms": 2000,
            "start_ms": 0,
            "end_ms": 2000,
            "interval_ms": 1000,
            "frames": [
                {"timestamp_ms": 0, "frame_index": 0, "filename": frame_names[0]},
                {"timestamp_ms": 1000, "frame_index": 30, "filename": frame_names[1]},
            ],
        }),
        encoding="utf-8",
    )

    window = MainWindow()
    try:
        window.annotation_manifest_input.setText(str(manifest_path))
        window._load_annotation_manifest()
        assert window.annotation_frame_list.count() == 2
        window.annotation_label_combo.setCurrentIndex(
            window.annotation_label_combo.findData("crosshair_off_target")
        )
        window.annotation_annotator_input.setText("reviewer")

        window.annotation_target_track_input.setText("Target-A")
        window.annotation_frame_preview.set_points((0.7, 0.5), (0.3, 0.5))
        window._save_frame_annotation()

        window.annotation_frame_list.setCurrentRow(1)
        app.processEvents()
        window.annotation_target_track_input.setText(" target-a ")
        window.annotation_frame_preview.set_points((0.3, 0.5), (0.7, 0.5))
        window._save_frame_annotation()

        dataset_path = frames_dir / "annotations.json"
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
        assert [item["target_track_id"] for item in dataset["annotations"]] == [
            "target-a", "target-a"
        ]
        assert "manual target-relative offset sign changes: horizontal 1, vertical 0" in (
            window.annotation_summary_label.text()
        )
        assert "eligible same-target pairs: 1" in window.annotation_summary_label.text()

        report_path = tmp_path / "transition-report.json"
        monkeypatch.setattr(
            "siegesense.ui.shell.QFileDialog.getSaveFileName",
            lambda *_args, **_kwargs: (
                str(report_path),
                "JSON report (*.json)",
            ),
        )
        window._export_aim_transition_report()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["summary"]["horizontal_sign_change_count"] == 1
        assert report["summary"]["vertical_sign_change_count"] == 0
        assert report["automatic_detection_used"] is False
        assert report["overshoot_diagnosed"] is False
        assert report["aim_accuracy_evaluated"] is False
        assert "does not diagnose overshoot" in window.annotation_status.text()
    finally:
        window.close()
