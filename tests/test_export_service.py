"""Tests for Markdown session-summary exports."""

from siegesense.domain.models import Observation, ObservationKind, Session
from siegesense.services.export_service import render_session_summary


def test_summary_contains_manual_notes_in_timestamp_order() -> None:
    session = Session(
        id="session-1", title="Ranked review", started_at="2026-10-25T10:00:00+00:00",
        media_path="C:/recordings/match.mp4", duration_ms=120_000,
    )
    later = Observation(
        id="note-2", session_id=session.id, timestamp_ms=83_000, text="Overshot target switch",
        kind=ObservationKind.AIM,
    )
    earlier = Observation(
        id="note-1", session_id=session.id, timestamp_ms=12_000, text="Rotated late",
        kind=ObservationKind.MOVEMENT,
    )

    result = render_session_summary(session, [later, earlier])

    assert "# Session review: Ranked review" in result
    assert "C:/recordings/match.mp4" in result
    assert "- **00:12 · Movement** — Rotated late" in result
    assert "- **01:23 · Aim** — Overshot target switch" in result
    assert result.index("Rotated late") < result.index("Overshot target switch")
    assert "not an automated gameplay analysis" in result


def test_empty_summary_does_not_invent_observations() -> None:
    result = render_session_summary(Session(title="Empty review"), [])
    assert "No observations were recorded" in result
    assert "Observations: 0" in result
