"""Tests for synchronising review notes with local video timestamps."""

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_use_playback_time_copies_current_position_to_observation(app: QApplication) -> None:
    database = Database(":memory:")
    window = MainWindow(session_service=SessionService(database))

    class FakePlayer:
        @staticmethod
        def position() -> int:
            return 83_750

    try:
        window.review_media_player = FakePlayer()
        window._set_observation_timestamp_from_video()
        assert window.observation_timestamp.value() == 83
        assert any(button.text() == "Use playback time" for button in window.findChildren(QPushButton))
    finally:
        window.close()
        database.close()
