"""Tests for category review and transparent coaching summaries."""

import pytest
from PySide6.QtWidgets import QApplication

from siegesense.domain.models import ObservationKind
from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_coach_summarises_manual_evidence_without_claiming_automatic_analysis(app: QApplication) -> None:
    database = Database(":memory:")
    service = SessionService(database)
    session = service.create_session("Ranked match")
    service.add_observation(session.id, 15_000, "Overshot during target switch", kind=ObservationKind.AIM, tags=("overshoot", "acog"))
    service.add_observation(session.id, 45_000, "Rotated late", kind=ObservationKind.MOVEMENT)
    window = MainWindow(session_service=service)
    try:
        prompts = [window.coach_prompt_list.item(i).text() for i in range(window.coach_prompt_list.count())]
        evidence = [window.coach_evidence_list.item(i).text() for i in range(window.coach_evidence_list.count())]
        assert any("Aim · 1 note(s)" in item for item in prompts)
        assert any("Movement · 1 note(s)" in item for item in prompts)
        assert any("not proof of a weakness" in item for item in prompts)
        assert any("Overshot during target switch" in item and "overshoot, acog" in item for item in evidence)
        assert any("Rotated late" in item for item in evidence)
        patterns = [window.coach_pattern_list.item(i).text() for i in range(window.coach_pattern_list.count())]
        assert any("Possible overflick / overshoot" in item for item in patterns)
        assert any("Single note" in item for item in patterns)
        assert "not a demonstrated weakness" in window.coach_pattern_detail.text()
    finally:
        window.close()
        database.close()


def test_aim_and_movement_pages_keep_separate_lists(app: QApplication) -> None:
    database = Database(":memory:")
    service = SessionService(database)
    session = service.create_session("Review")
    service.add_observation(session.id, 1_000, "Crosshair too low", kind=ObservationKind.AIM, tags=("placement",))
    service.add_observation(session.id, 2_000, "Exposed during rotation", kind=ObservationKind.MOVEMENT)
    window = MainWindow(session_service=service)
    try:
        aim_list = window._category_observation_lists["aim"]
        movement_list = window._category_observation_lists["movement"]
        assert aim_list is not movement_list
        assert any("Crosshair too low" in aim_list.item(i).text() for i in range(aim_list.count()))
        assert not any("Exposed during rotation" in aim_list.item(i).text() for i in range(aim_list.count()))
        assert any("Exposed during rotation" in movement_list.item(i).text() for i in range(movement_list.count()))
        assert not any("Crosshair too low" in movement_list.item(i).text() for i in range(movement_list.count()))
        window._category_filter_inputs["aim"].setText("placement")
        assert any("Crosshair too low" in aim_list.item(i).text() for i in range(aim_list.count()))
        assert not any("Exposed during rotation" in aim_list.item(i).text() for i in range(aim_list.count()))
        window._category_filter_inputs["aim"].setText("does-not-exist")
        assert "No observations match" in aim_list.item(0).text()
    finally:
        window.close()
        database.close()


def test_coach_empty_state_asks_for_observations(app: QApplication) -> None:
    database = Database(":memory:")
    window = MainWindow(session_service=SessionService(database))
    try:
        assert "Start with one recorded match" in window.coach_prompt_list.item(0).text()
        assert "No real-session observations" in window.coach_evidence_list.item(0).text()
    finally:
        window.close()
        database.close()
