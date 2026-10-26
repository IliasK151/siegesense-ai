"""Tests for transparent evidence-based coaching suggestions."""

from siegesense.domain.models import ObservationKind
from siegesense.services.coaching_service import build_coaching_insights
from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database


def test_single_manual_tag_produces_a_hypothesis_not_a_diagnosis() -> None:
    with Database(":memory:") as database:
        service = SessionService(database)
        session = service.create_session("Match A")
        observation = service.add_observation(
            session.id,
            12_000,
            "Overshot during a target switch",
            kind=ObservationKind.AIM,
            tags=("overshoot", "acog"),
        )

        insights = build_coaching_insights([(session, observation)])

    assert len(insights) == 1
    assert insights[0].key == "overflick"
    assert insights[0].observation_count == 1
    assert insights[0].session_count == 1
    assert insights[0].evidence_level == "Single note"
    assert "not a demonstrated weakness" in insights[0].summary
    assert "keep your current sensitivity" in insights[0].drill


def test_aliases_aggregate_across_sessions_without_duplicate_counting() -> None:
    with Database(":memory:") as database:
        service = SessionService(database)
        first = service.create_session("Match A", started_at="2026-01-01T00:00:00+00:00")
        second = service.create_session("Match B", started_at="2026-01-02T00:00:00+00:00")
        one = service.add_observation(
            first.id, 10_000, "Passed the target", kind=ObservationKind.AIM,
            tags=("overshoot", "overflick"),
        )
        two = service.add_observation(
            second.id, 20_000, "Needed correction", kind=ObservationKind.AIM,
            tags=("overflick",),
        )

        insights = build_coaching_insights([(first, one), (second, two)])

    assert len(insights) == 1
    insight = insights[0]
    assert insight.observation_count == 2
    assert insight.session_count == 2
    assert insight.evidence_level == "Recurring across sessions"
    assert "2 sessions" in insight.summary
    assert "not proof of cause" in insight.summary
    assert insight.evidence[0][0].id == second.id


def test_repeated_tag_in_only_one_session_is_not_called_recurring() -> None:
    with Database(":memory:") as database:
        service = SessionService(database)
        session = service.create_session("Match A")
        first = service.add_observation(
            session.id, 10_000, "Passed target", kind=ObservationKind.AIM, tags=("overflick",)
        )
        second = service.add_observation(
            session.id, 20_000, "Passed target again", kind=ObservationKind.AIM,
            tags=("overflick",),
        )

        insight = build_coaching_insights([(session, first), (session, second)])[0]

    assert insight.observation_count == 2
    assert insight.session_count == 1
    assert insight.evidence_level == "Repeated in one session"
    assert "another match" in insight.summary


def test_free_text_and_unknown_tags_do_not_generate_automatic_claims() -> None:
    with Database(":memory:") as database:
        service = SessionService(database)
        session = service.create_session("Match A")
        observation = service.add_observation(
            session.id, 10_000, "I think I overflicked", kind=ObservationKind.AIM,
            tags=("acog", "close-range"),
        )

        insights = build_coaching_insights([(session, observation)])

    assert insights == []


def test_each_issue_uses_one_note_even_when_multiple_aliases_are_present() -> None:
    with Database(":memory:") as database:
        service = SessionService(database)
        session = service.create_session("Match A")
        observation = service.add_observation(
            session.id, 10_000, "Reticle endpoint passed target", kind=ObservationKind.AIM,
            tags=("overflick", "overshoot", "over flick"),
        )

        insights = build_coaching_insights([(session, observation)])

    assert insights[0].observation_count == 1
