"""Tests for overview counts and evidence-based review focus."""

import pytest
from PySide6.QtWidgets import QApplication

from siegesense.domain.models import ObservationKind
from siegesense.services.session_service import SessionService
from siegesense.services.settings_service import SettingsService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_overview_counts_only_real_sessions_and_observations(app: QApplication) -> None:
    database = Database(":memory:")
    sessions = SessionService(database)
    settings = SettingsService(database)
    real = sessions.create_session("Real review", media_path="/tmp/match.mp4")
    sessions.add_observation(real.id, 12_000, "Overshot a target", kind=ObservationKind.AIM)
    sessions.add_observation(real.id, 18_000, "Rotated late", kind=ObservationKind.MOVEMENT)
    demo = sessions.create_session("Demo review", is_demo=True)
    sessions.add_observation(demo.id, 3_000, "Demo note", kind=ObservationKind.AIM)
    baseline = settings.save_snapshot("Baseline", {"horizontal": 6})
    settings.create_experiment("Sensitivity test", "Check control", baseline.id)
    demo_baseline = settings.save_snapshot("Demo baseline", {"horizontal": 9}, is_demo=True)
    settings.create_experiment("Demo test", "Example only", demo_baseline.id, is_demo=True)

    window = MainWindow(session_service=sessions, settings_service=settings)
    try:
        values = {key: label.text() for key, label in window._overview_metric_values.items()}
        assert values == {"sessions": "1", "observations": "2", "experiments": "1", "recordings": "1"}
        activity = [window.overview_activity_list.item(i).text() for i in range(window.overview_activity_list.count())]
        assert len(activity) == 1
        assert "Real review" in activity[0]
        assert all("Demo" not in item for item in activity)
        priorities = [window.overview_priority_list.item(i).text() for i in range(window.overview_priority_list.count())]
        assert any("Aim  ·  1 observation logged" in item for item in priorities)
        assert any("Movement  ·  1 observation logged" in item for item in priorities)
        assert any("not an automated assessment" in item for item in priorities)
    finally:
        window.close()
        database.close()


def test_overview_empty_state_is_explicit(app: QApplication) -> None:
    database = Database(":memory:")
    window = MainWindow(
        session_service=SessionService(database), settings_service=SettingsService(database)
    )
    try:
        assert {key: label.text() for key, label in window._overview_metric_values.items()} == {
            "sessions": "0", "observations": "0", "experiments": "0", "recordings": "0"
        }
        assert "No sessions saved yet" in window.overview_activity_list.item(0).text()
        assert "No review focus yet" in window.overview_priority_list.item(0).text()
    finally:
        window.close()
        database.close()
