"""Integration tests for the graphical local clip annotation workflow."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_annotation_workspace_loads_frame_and_persists_label(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        assert "off target: 1" in window.annotation_summary_label.text()
        assert "consecutive off-target runs: 1" in window.annotation_summary_label.text()
        assert "not aim accuracy" in window.annotation_summary_label.text()

        report_path = frames_dir / "evaluation-report.json"
        monkeypatch.setattr(
            "siegesense.ui.shell.QFileDialog.getSaveFileName",
            lambda *_args, **_kwargs: (str(report_path), "JSON report (*.json)"),
        )
        window._export_annotation_report()
        assert report_path.is_file()
        exported = json.loads(report_path.read_text(encoding="utf-8"))
        assert exported["model_performance_evaluated"] is False
        assert "does not measure model performance" in window.annotation_status.text()

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
        assert "on target: 0" in window.annotation_summary_label.text()
        assert "off target: 0" in window.annotation_summary_label.text()
        assert "consecutive off-target runs: 0" in window.annotation_summary_label.text()
    finally:
        window.close()


def test_annotation_workspace_samples_local_recording(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "gameplay.mp4"
    source.write_bytes(b"test recording")
    output = tmp_path / "sampled-frames"

    def fake_sample_video_frames(source_path, output_dir, *, interval_ms):
        destination = Path(output_dir)
        destination.mkdir(parents=True)
        frame_name = "frame_000000000ms.png"
        frame = QPixmap(320, 180)
        frame.fill(Qt.GlobalColor.darkCyan)
        assert frame.save(str(destination / frame_name))
        (destination / "sampling_manifest.json").write_text(json.dumps({
            "schema_version": 1,
            "source_path": str(source_path),
            "source_sha256": "fake-sampling-fingerprint",
            "source_fps": 30.0,
            "source_width": 320,
            "source_height": 180,
            "duration_ms": 1000,
            "start_ms": 0,
            "end_ms": 1000,
            "interval_ms": interval_ms,
            "frames": [{"timestamp_ms": 0, "frame_index": 0, "filename": frame_name}],
        }), encoding="utf-8")
        return SimpleNamespace(
            frames=(SimpleNamespace(timestamp_ms=0, filename=frame_name),),
            interval_ms=interval_ms,
        )

    monkeypatch.setattr("siegesense.ui.shell.sample_video_frames", fake_sample_video_frames)
    window = MainWindow()
    try:
        window.annotation_video_input.setText(str(source))
        window.annotation_output_input.setText(str(output))
        window.annotation_interval_spin.setValue(150)
        window._sample_annotation_video()
        assert window.annotation_frame_list.count() == 1
        assert "Sampled 1 frame(s) at 150 ms intervals" in window.annotation_status.text()
        assert window.annotation_manifest_input.text() == str(output / "sampling_manifest.json")
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
    session = service.create_session(
        "Link test session",
        duration_ms=5000,
        media_path=str(tmp_path / "link-clip.mp4"),
    )
    mismatched_session = service.create_session(
        "Different recording",
        duration_ms=5000,
        media_path=str(tmp_path / "different-clip.mp4"),
    )
    window = MainWindow(session_service=service)
    try:
        window.show_page("Clip Annotation")
        assert window.annotation_session_combo.count() == 2
        window.annotation_session_combo.setCurrentIndex(
            window.annotation_session_combo.findData(session.id)
        )
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
        assert any(tag.startswith("annotation-id:") for tag in observations[0].tags)
        assert window.page_stack.currentWidget() is not None
        assert "Session Review" in window.breadcrumb.text()

        window.show_page("Clip Annotation")
        window.annotation_history_list.setCurrentRow(0)
        window.annotation_session_combo.setCurrentIndex(
            window.annotation_session_combo.findData(session.id)
        )
        window._link_annotation_to_session()
        assert len(service.list_observations(session.id)) == 1
        assert "already linked" in window.annotation_status.text().lower()

        window.annotation_session_combo.setCurrentIndex(
            window.annotation_session_combo.findData(mismatched_session.id)
        )
        window._link_annotation_to_session()
        assert service.list_observations(mismatched_session.id) == []
        assert "does not match" in window.annotation_status.text().lower()

        window.annotation_session_combo.setCurrentIndex(
            window.annotation_session_combo.findData(session.id)
        )
        window._link_annotation_to_session()
        window.show_page("Session Review")
        window.review_session_combo.setCurrentIndex(
            window.review_session_combo.findData(session.id)
        )
        window.observation_list.setCurrentRow(0)
        window._open_linked_annotation_frame()
        assert "Clip Annotation" in window.breadcrumb.text()
        assert window.annotation_frame_list.currentItem() is not None
        assert window.annotation_frame_list.currentItem().data(Qt.ItemDataRole.UserRole) == (0, frame_name)

        window.show_page("Session Review")
        window.review_session_combo.setCurrentIndex(
            window.review_session_combo.findData(session.id)
        )
        window.observation_list.setCurrentRow(0)
        window._annotation_store = None
        window._open_linked_annotation_frame()
        assert "matching sampling manifest" in window.review_status.text().lower()
    finally:
        window.close()
        database.close()



def test_annotation_workspace_marks_and_updates_spatial_points(
    app: QApplication, tmp_path: Path
) -> None:
    frames_dir = tmp_path / "sampled-points"
    frames_dir.mkdir()
    frame_name = "frame_000000000ms.png"
    image = QPixmap(320, 180)
    image.fill(Qt.GlobalColor.darkBlue)
    assert image.save(str(frames_dir / frame_name))
    manifest_path = frames_dir / "sampling_manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "source_path": str(tmp_path / "clip-points.mp4"),
        "source_sha256": "points-test-fingerprint",
        "source_fps": 30.0,
        "source_width": 320,
        "source_height": 180,
        "duration_ms": 1000,
        "start_ms": 0,
        "end_ms": 1000,
        "interval_ms": 100,
        "frames": [{"timestamp_ms": 0, "frame_index": 0, "filename": frame_name}],
    }), encoding="utf-8")

    window = MainWindow()
    window.resize(1300, 900)
    window.show()
    app.processEvents()
    try:
        window.annotation_manifest_input.setText(str(manifest_path))
        window._load_annotation_manifest()
        app.processEvents()
        picker = window.annotation_frame_preview
        rect = picker.displayed_image_rect()
        assert not rect.isEmpty()

        window.annotation_mark_reticle_button.click()
        app.processEvents()
        rect = picker.displayed_image_rect()
        QTest.mouseClick(
            picker, Qt.MouseButton.LeftButton,
            pos=QPoint(round(rect.x() + rect.width() * 0.3),
                       round(rect.y() + rect.height() * 0.4)),
        )
        window.annotation_mark_target_button.click()
        app.processEvents()
        rect = picker.displayed_image_rect()
        QTest.mouseClick(
            picker, Qt.MouseButton.LeftButton,
            pos=QPoint(round(rect.x() + rect.width() * 0.7),
                       round(rect.y() + rect.height() * 0.6)),
        )
        window._save_frame_annotation()

        dataset_path = frames_dir / "annotations.json"
        saved = json.loads(dataset_path.read_text(encoding="utf-8"))["annotations"][0]
        assert saved["reticle_x"] == pytest.approx(0.3, abs=0.02)
        assert saved["reticle_y"] == pytest.approx(0.4, abs=0.02)
        assert saved["target_x"] == pytest.approx(0.7, abs=0.02)
        assert saved["target_y"] == pytest.approx(0.6, abs=0.02)
        assert "manual reticle/target point pairs: 1" in window.annotation_summary_label.text()

        window.annotation_history_list.setCurrentRow(0)
        window.annotation_clear_points_button.click()
        window._update_selected_annotation()
        updated = json.loads(dataset_path.read_text(encoding="utf-8"))["annotations"][0]
        assert updated["reticle_x"] is None
        assert updated["reticle_y"] is None
        assert updated["target_x"] is None
        assert updated["target_y"] is None
    finally:
        window.close()
