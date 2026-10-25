"""Render portable, evidence-only session review summaries."""

from __future__ import annotations

import csv
import io
import json

from siegesense.domain.models import Observation, Session


def render_session_summary(session: Session, observations: list[Observation]) -> str:
    """Render a Markdown summary from a session and its timestamped notes.

    The export deliberately includes only manually recorded observations. It does
    not invent performance metrics or infer a result from missing evidence.
    """
    lines = [
        f"# Session review: {session.title}",
        "",
        f"- Started: {session.started_at}",
        f"- Duration: {session.duration_ms / 1000:.1f} seconds" if session.duration_ms is not None else "- Duration: not recorded",
        f"- Recording: {session.media_path}" if session.media_path else "- Recording: not linked",
        f"- Observations: {len(observations)}",
        "",
        "## Timestamped observations",
        "",
    ]
    ordered = sorted(observations, key=lambda item: (item.timestamp_ms, item.created_at))
    if not ordered:
        lines.append("No observations were recorded for this session.")
    else:
        for observation in ordered:
            seconds = observation.timestamp_ms // 1000
            timestamp = f"{seconds // 60:02d}:{seconds % 60:02d}"
            tag_suffix = f" · Tags: {', '.join(observation.tags)}" if observation.tags else ""
            lines.append(f"- **{timestamp} · {observation.kind.value.title()}** — {observation.text}{tag_suffix}")
    lines.extend(
        [
            "",
            "---",
            "Export contains user-recorded notes only. It is not an automated gameplay analysis or proof of improvement.",
            "",
        ]
    )
    return "\n".join(lines)



def render_session_json(session: Session, observations: list[Observation]) -> str:
    """Render structured JSON containing only the selected session and its notes."""
    payload = {
        "session": {
            "id": session.id,
            "title": session.title,
            "started_at": session.started_at,
            "duration_ms": session.duration_ms,
            "media_path": session.media_path,
        },
        "observations": [
            {
                "id": item.id,
                "timestamp_ms": item.timestamp_ms,
                "kind": item.kind.value,
                "text": item.text,
                "tags": list(item.tags),
                "created_at": item.created_at,
            }
            for item in sorted(observations, key=lambda note: (note.timestamp_ms, note.created_at))
        ],
        "limitations": "User-recorded notes only; not automated gameplay analysis or proof of improvement.",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_session_csv(observations: list[Observation]) -> str:
    """Render timestamped observations as a portable CSV table."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["timestamp_ms", "timestamp", "category", "text", "tags", "created_at"])
    for item in sorted(observations, key=lambda note: (note.timestamp_ms, note.created_at)):
        seconds = item.timestamp_ms // 1000
        timestamp = f"{seconds // 60:02d}:{seconds % 60:02d}"
        writer.writerow([item.timestamp_ms, timestamp, item.kind.value, item.text, "|".join(item.tags), item.created_at])
    return buffer.getvalue()
