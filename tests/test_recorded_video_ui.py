"""Tests for safe local recording selection in Session Review."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_existing_local_recording_is_loaded_into_player(app: QApplication, tmp_path: Path) -> None:
    recording = tmp_path / "match.mp4"
    recording.write_bytes(b"test media placeholder")
    database = Database(":memory:")
    service = SessionService(database)
    session = service.create_session("Recorded match", media_path=str(recording))
    window = MainWindow(session_service=service)
    try:
        assert window.review_session_combo.currentData() == session.id
        assert window.review_media_player.source().toLocalFile() == str(recording.resolve())
        assert "Loaded local recording" in window.review_media_status.text()
    finally:
        window.close()
        database.close()


def test_missing_local_recording_is_reported_without_starting_playback(app: QApplication, tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    database = Database(":memory:")
    service = SessionService(database)
    service.create_session("Missing recording", media_path=str(missing))
    window = MainWindow(session_service=service)
    try:
        assert window.review_media_player.source().isEmpty()
        assert "file not found" in window.review_media_status.text().lower()
    finally:
        window.close()
        database.close()
