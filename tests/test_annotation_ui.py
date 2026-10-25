"""Integration tests for the graphical local clip annotation workflow."""
import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database
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
        assert window.annotation_frame_counter.text() == "Frame 1 of 1"
        assert not window.annotation_previous_button.isEnabled()
        assert not window.annotation_next_button.isEnabled()

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
        window.annotation_label_combo.setCurrentIndex(
            window.annotation_label_combo.findData("crosshair_on_target")
        )
        window.annotation_note_input.setText("corrected after replay")
        window._update_selected_annotation()
        edited = json.loads(dataset_path.read_text(encoding="utf-8"))["annotations"][0]
        assert edited["label"] == "crosshair_on_target"
        assert edited["note"] == "corrected after replay"
        assert "Updated" in window.annotation_status.text()

        window.annotation_history_list.setCurrentRow(0)
        window._delete_selected_annotation()
        assert window.annotation_history_list.count() == 0
        assert json.loads(dataset_path.read_text(encoding="utf-8"))["annotations"] == []
        assert "deleted" in window.annotation_status.text().lower()
    finally:
        window.close()


def test_saved_annotation_can_be_linked_to_real_session(app: QApplication, tmp_path: Path) -> None:
    frames_dir = tmp_path / "sampled-link"
    frames_dir.mkdir()
    frame_name = "frame_000000000ms.png"
    pixmap = QPixmap(320, 180)
    pixmap.fill(Qt.GlobalColor.darkGreen)
    assert pixmap.save(str(frames_dir / frame_name))
    manifest_path = frames_dir / "sampling_manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "source_path": str(tmp_path / "link-clip.mp4"),
        "source_sha256": "link-test-fingerprint",
        "source_fps": 30.0,
        "source_width": 320,
        "source_height": 180,
        "duration_ms": 5000,
        "start_ms": 0,
        "end_ms": 5000,
        "interval_ms": 1000,
        "frames": [{"timestamp_ms": 0, "frame_index": 0, "filename": frame_name}],
    }), encoding="utf-8")

    database = Database(":memory:")
    service = SessionService(database)
    session = service.create_session("Link test session", duration_ms=5000)
    window = MainWindow(session_service=service)
    try:
        window.show_page("Clip Annotation")
        assert window.annotation_session_combo.currentData() == session.id
        window.annotation_manifest_input.setText(str(manifest_path))
        window._load_annotation_manifest()
        window.annotation_label_combo.setCurrentIndex(
            window.annotation_label_combo.findData("crosshair_off_target")
        )
        window.annotation_annotator_input.setText("reviewer")
        window.annotation_note_input.setText("overshot target")
        window._save_frame_annotation()
        window.annotation_history_list.setCurrentRow(0)
        window._link_annotation_to_session()

        observations = service.list_observations(session.id)
        assert len(observations) == 1
        assert observations[0].timestamp_ms == 0
        assert observations[0].kind.value == "aim"
        assert "crosshair off target" in observations[0].text
        assert "overshot target" in observations[0].text
        assert "clip-annotation" in observations[0].tags
        assert window.page_stack.currentWidget() is not None
        assert "Session Review" in window.breadcrumb.text()
    finally:
        window.close()
        database.close()
