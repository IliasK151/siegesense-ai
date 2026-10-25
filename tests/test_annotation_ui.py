"""Integration tests for the graphical local clip annotation workflow."""
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


def test_annotation_workspace_loads_frame_and_persists_label(app: QApplication, tmp_path: Path) -> None:
    frames_dir = tmp_path / "sampled"
    frames_dir.mkdir()
    frame_name = "frame_000000000ms.png"
    pixmap = QPixmap(320, 180)
    pixmap.fill(Qt.GlobalColor.darkBlue)
    assert pixmap.save(str(frames_dir / frame_name))
    manifest_path = frames_dir / "sampling_manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "source_path": str(tmp_path / "clip.mp4"),
        "source_sha256": "test-fingerprint",
        "source_fps": 30.0,
        "source_width": 320,
        "source_height": 180,
        "duration_ms": 1000,
        "start_ms": 0,
        "end_ms": 1000,
        "interval_ms": 1000,
        "frames": [{"timestamp_ms": 0, "frame_index": 0, "filename": frame_name}],
    }), encoding="utf-8")

    window = MainWindow()
    try:
        window.annotation_manifest_input.setText(str(manifest_path))
        window._load_annotation_manifest()
        assert window.annotation_frame_list.count() == 1
        assert window.annotation_frame_list.currentItem() is not None
        assert not window.annotation_frame_preview.pixmap().isNull()

        window.annotation_label_combo.setCurrentIndex(
            window.annotation_label_combo.findData("crosshair_off_target")
        )
        window.annotation_annotator_input.setText("reviewer")
        window.annotation_note_input.setText("crosshair moved past target")
        window._save_frame_annotation()

        dataset_path = frames_dir / "annotations.json"
        assert dataset_path.is_file()
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
        assert dataset["source_sha256"] == "test-fingerprint"
        assert dataset["annotations"][0]["label"] == "crosshair_off_target"
        assert "crosshair off target" in window.annotation_history_list.item(0).text()
        assert "Saved" in window.annotation_status.text()

        window.annotation_history_list.setCurrentRow(0)
        window._delete_selected_annotation()
        assert window.annotation_history_list.count() == 0
        assert json.loads(dataset_path.read_text(encoding="utf-8"))["annotations"] == []
        assert "deleted" in window.annotation_status.text().lower()
    finally:
        window.close()
