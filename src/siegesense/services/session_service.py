"""Application service for creating sessions and timestamped observations."""

from __future__ import annotations

import hashlib
from pathlib import Path

from siegesense.domain.models import Observation, ObservationKind, Session, utc_now_iso
from siegesense.storage.database import Database


class SessionService:
    """Coordinate session workflows without coupling the UI to SQL."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_session(
        self,
        title: str,
        *,
        started_at: str | None = None,
        duration_ms: int | None = None,
        media_path: str | None = None,
        notes: str = "",
        is_demo: bool = False,
    ) -> Session:
        """Validate and persist a new session, returning the stored record."""
        session = Session(
            title=title,
            started_at=started_at if started_at is not None else utc_now_iso(),
            duration_ms=duration_ms,
            media_path=media_path,
            notes=notes,
            is_demo=is_demo,
        )
        self._database.add_session(session)
        return session

    def fingerprint_session_media(self, session_id: str, *, chunk_size: int = 1024 * 1024) -> str:
        """Hash a session recording on demand and persist its SHA-256 fingerprint."""
        if chunk_size < 1:
            raise ValueError("Chunk size must be greater than zero")
        session = self._database.get_session(session_id)
        if session is None:
            raise ValueError("Session does not exist")
        if not session.media_path:
            raise ValueError("Session has no recording path")
        path = Path(session.media_path).expanduser()
        if not path.is_file():
            raise ValueError("Session recording file does not exist")
        digest = hashlib.sha256()
        with path.open("rb") as media_file:
            for chunk in iter(lambda: media_file.read(chunk_size), b""):
                digest.update(chunk)
        fingerprint = digest.hexdigest()
        self._database.set_session_media_sha256(session_id, fingerprint)
        return fingerprint

    def list_sessions(self, *, include_demo: bool = False) -> list[Session]:
        """List recent sessions; demo records are excluded by default."""
        return self._database.list_sessions(include_demo=include_demo)

    def add_observation(
        self,
        session_id: str,
        timestamp_ms: int,
        text: str,
        *,
        kind: ObservationKind = ObservationKind.OTHER,
        tags: tuple[str, ...] = (),
    ) -> Observation:
        """Add a timestamped note using the parent session's provenance."""
        session = self._database.get_session(session_id)
        if session is None:
            raise ValueError("Session does not exist")
        observation = Observation(
            session_id=session.id,
            timestamp_ms=timestamp_ms,
            text=text,
            kind=kind,
            tags=tags,
            is_demo=session.is_demo,
        )
        self._database.add_observation(observation)
        return observation

    def list_observations(
        self, session_id: str, *, include_demo: bool = False
    ) -> list[Observation]:
        """List observations in timestamp order, respecting demo isolation."""
        if self._database.get_session(session_id) is None:
            raise ValueError("Session does not exist")
        return self._database.list_observations(session_id, include_demo=include_demo)
