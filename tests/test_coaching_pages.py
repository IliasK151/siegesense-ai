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
        assert not window.coach_plan_experiment_button.isEnabled()
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



def test_session_review_quick_tag_appends_without_duplicates(app: QApplication) -> None:
    database = Database(":memory:")
    service = SessionService(database)
    service.create_session("Review")
    window = MainWindow(session_service=service)
    try:
        window.observation_tags_input.setText("acog")
        window.coaching_tag_combo.setCurrentIndex(
            window.coaching_tag_combo.findData("overflick")
        )
        window.add_coaching_tag_button.click()
        assert window.observation_tags_input.text() == "acog, overflick"
        window.add_coaching_tag_button.click()
        assert window.observation_tags_input.text() == "acog, overflick"
    finally:
        window.close()
        database.close()



def test_recurring_aim_pattern_prepares_a_one_variable_settings_experiment(app: QApplication) -> None:
    from siegesense.services.settings_service import SettingsService

    database = Database(":memory:")
    session_service = SessionService(database)
    first = session_service.create_session(
        "Ranked A", started_at="2026-01-01T00:00:00+00:00"
    )
    second = session_service.create_session(
        "Ranked B", started_at="2026-01-02T00:00:00+00:00"
    )
    session_service.add_observation(
        first.id, 10_000, "Reticle passed the target", kind=ObservationKind.AIM,
        tags=("overflick", "acog"),
    )
    session_service.add_observation(
        second.id, 20_000, "Similar reticle overshoot", kind=ObservationKind.AIM,
        tags=("overflick", "acog"),
    )
    window = MainWindow(
        session_service=session_service,
        settings_service=SettingsService(database),
    )
    try:
        assert window.coach_plan_experiment_button.isEnabled()
        window.coach_plan_experiment_button.click()
        assert window.breadcrumb.text() == "Workspace  /  Settings Lab"
        assert window.experiment_title_input.text() == (
            "Coach follow-up: Possible overflick / overshoot"
        )
        assert window.experiment_variable_input.text() == "2.5x ADS sensitivity"
        assert "test hypothesis, not" in window.experiment_hypothesis_input.text()
        assert "Verify the displayed fields against your actual in-game settings" in window.settings_status.text()
    finally:
        window.close()
        database.close()
