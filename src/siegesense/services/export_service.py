"""Render portable, evidence-only session review summaries."""

from __future__ import annotations

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
            lines.append(f"- **{timestamp} · {observation.kind.value.title()}** — {observation.text}")
    lines.extend(
        [
            "",
            "---",
            "Export contains user-recorded notes only. It is not an automated gameplay analysis or proof of improvement.",
            "",
        ]
    )
    return "\\n".join(lines)
