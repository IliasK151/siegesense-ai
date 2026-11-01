"""Local SQLite storage. Everything stays on the player's PC."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .profile import Profile

if TYPE_CHECKING:
    from .warmup import HistoryPoint, WarmupSummary

# Ordered migrations; index + 1 is the schema version. Later steps append here.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE profiles (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        data TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE warmup_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        duration_s REAL NOT NULL,
        score INTEGER,
        summary TEXT NOT NULL
    );
    """,
]


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._migrate()

    def _migrate(self) -> None:
        with self._lock, self._db:
            self._db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            current = self._version_unlocked()
            for version, sql in enumerate(MIGRATIONS[current:], start=current + 1):
                self._db.executescript(sql)
                self._db.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                    (str(version),),
                )

    def _version_unlocked(self) -> int:
        row = self._db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        return int(row[0]) if row else 0

    def schema_version(self) -> int:
        with self._lock:
            return self._version_unlocked()

    def get_profile(self) -> Profile | None:
        with self._lock:
            row = self._db.execute("SELECT data FROM profiles WHERE id = 1").fetchone()
        return Profile.model_validate_json(row[0]) if row else None

    def save_profile(self, profile: Profile) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO profiles (id, data, updated_at) VALUES (1, ?, ?)",
                (profile.model_dump_json(), datetime.now(UTC).isoformat()),
            )

    def add_warmup(self, summary: WarmupSummary) -> int:
        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT INTO warmup_sessions (started_at, duration_s, score, summary) "
                "VALUES (?, ?, ?, ?)",
                (
                    summary.started_at,
                    summary.duration_s,
                    summary.metrics.score,
                    summary.model_dump_json(),
                ),
            )
            return int(cur.lastrowid)

    def recent_warmups(self, limit: int = 7) -> list[HistoryPoint]:
        from .warmup import HistoryPoint

        with self._lock:
            rows = self._db.execute(
                "SELECT started_at, score FROM warmup_sessions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [HistoryPoint(started_at=r[0], score=r[1]) for r in reversed(rows)]

    def close(self) -> None:
        with self._lock:
            self._db.close()
