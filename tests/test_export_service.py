"""Tests for Markdown session-summary exports."""

from siegesense.domain.models import Observation, ObservationKind, Session
from siegesense.services.export_service import render_session_csv, render_session_json, render_session_summary
import csv
import io
import json


def test_summary_contains_manual_notes_in_timestamp_order() -> None:
    session = Session(
        id="session-1", title="Ranked review", started_at="2026-10-25T10:00:00+00:00",
        media_path="C:/recordings/match.mp4", duration_ms=120_000,
    )
    later = Observation(
        id="note-2", session_id=session.id, timestamp_ms=83_000, text="Overshot target switch",
        kind=ObservationKind.AIM, tags=("overshoot", "acog"),
    )
    earlier = Observation(
        id="note-1", session_id=session.id, timestamp_ms=12_000, text="Rotated late",
        kind=ObservationKind.MOVEMENT,
    )

    result = render_session_summary(session, [later, earlier])

    assert "# Session review: Ranked review" in result
    assert "C:/recordings/match.mp4" in result
    assert "- **00:12 · Movement** — Rotated late" in result
    assert "- **01:23 · Aim** — Overshot target switch · Tags: overshoot, acog" in result
    assert result.index("Rotated late") < result.index("Overshot target switch")
    assert "not an automated gameplay analysis" in result


def test_empty_summary_does_not_invent_observations() -> None:
    result = render_session_summary(Session(title="Empty review"), [])
    assert "No observations were recorded" in result
    assert "Observations: 0" in result



def test_json_export_preserves_tags_and_timestamp_units() -> None:
    session = Session(id="session-json", title="JSON review")
    note = Observation(
        id="note-json", session_id=session.id, timestamp_ms=83_000,
        text="Overshot", kind=ObservationKind.AIM, tags=("overshoot", "acog"),
    )

    payload = json.loads(render_session_json(session, [note]))

    assert payload["session"]["id"] == "session-json"
    assert payload["observations"][0]["timestamp_ms"] == 83_000
    assert payload["observations"][0]["tags"] == ["overshoot", "acog"]
    assert "not automated gameplay analysis" in payload["limitations"]


def test_csv_export_escapes_commas_and_preserves_tags() -> None:
    note = Observation(
        id="note-csv", session_id="session-csv", timestamp_ms=83_000,
        text="Overshot, then corrected", kind=ObservationKind.AIM, tags=("overshoot", "acog"),
    )

    rows = list(csv.DictReader(io.StringIO(render_session_csv([note]))))

    assert len(rows) == 1
    assert rows[0]["timestamp_ms"] == "83000"
    assert rows[0]["timestamp"] == "01:23"
    assert rows[0]["text"] == "Overshot, then corrected"
    assert rows[0]["tags"] == "overshoot|acog"
