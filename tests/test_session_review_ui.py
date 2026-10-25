"""Integration tests for session-review controls backed by local storage."""

import pytest
from PySide6.QtWidgets import QApplication

from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_session_review_creates_session_and_timestamped_observation(app: QApplication) -> None:
    database = Database(":memory:")
    window = MainWindow(session_service=SessionService(database))
    try:
        window.session_title_input.setText("Ranked review")
        window.session_media_input.setText("C:/recordings/match.mp4")
        window._create_review_session()

        sessions = window.session_service.list_sessions()
        assert len(sessions) == 1
        session = sessions[0]
        assert session.title == "Ranked review"
        assert session.media_path == "C:/recordings/match.mp4"
        assert window.review_session_combo.currentData() == session.id

        window.observation_timestamp.setValue(83)
        window.observation_kind.setCurrentIndex(window.observation_kind.findData("aim"))
        window.observation_text.setText("Overshot during target transition")
        window._add_review_observation()

        observations = window.session_service.list_observations(session.id)
        assert len(observations) == 1
        assert observations[0].timestamp_ms == 83_000
        assert observations[0].text == "Overshot during target transition"
        assert observations[0].kind.value == "aim"
        assert window.observation_list.count() == 1
        assert "01:23" in window.observation_list.item(0).text()
    finally:
        window.close()
        database.close()


def test_session_review_does_not_display_demo_sessions(app: QApplication) -> None:
    database = Database(":memory:")
    service = SessionService(database)
    service.create_session("Real session")
    service.create_session("Demo session", is_demo=True)
    window = MainWindow(session_service=service)
    try:
        labels = [window.review_session_combo.itemText(i) for i in range(window.review_session_combo.count())]
        assert labels == ["Real session"]
    finally:
        window.close()
        database.close()
