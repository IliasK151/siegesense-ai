"""SQLite persistence with schema versioning and demo-data isolation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from siegesense.domain.models import MetricResult, Observation, ObservationKind, Session, SettingsExperiment, SettingsSnapshot

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, started_at TEXT NOT NULL, duration_ms INTEGER,
    media_path TEXT, notes TEXT NOT NULL DEFAULT '', is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1)),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_real_started ON sessions(is_demo, started_at);
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp_ms INTEGER NOT NULL CHECK (timestamp_ms >= 0), text TEXT NOT NULL, kind TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
    is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_observations_session_time ON observations(session_id, timestamp_ms);
CREATE TABLE IF NOT EXISTS metric_results (
    id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    name TEXT NOT NULL, unit TEXT NOT NULL, source TEXT NOT NULL, method TEXT NOT NULL, value REAL,
    validity TEXT NOT NULL, confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    notes TEXT NOT NULL DEFAULT '', is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1)), measured_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings_snapshots (
    id TEXT PRIMARY KEY, label TEXT NOT NULL, values_json TEXT NOT NULL, created_at TEXT NOT NULL,
    is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1))
);
CREATE TABLE IF NOT EXISTS settings_experiments (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, hypothesis TEXT NOT NULL,
    baseline_snapshot_id TEXT NOT NULL REFERENCES settings_snapshots(id), changed_variable TEXT NOT NULL DEFAULT '',
    test_snapshot_id TEXT REFERENCES settings_snapshots(id), outcome TEXT, notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('planned', 'running', 'completed', 'inconclusive', 'cancelled')),
    created_at TEXT NOT NULL, is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1))
);
CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""


class Database:
    """Manage a local SQLite file and provide narrow repository methods."""

    def __init__(self, path: str | Path) -> None:
        raw_path = str(path)
        self.path = Path(raw_path)
        if raw_path != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(raw_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        current = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise RuntimeError(f"Database schema {current} is newer than supported {SCHEMA_VERSION}")
        if current < 1:
            with self._connection:
                self._connection.executescript(_SCHEMA)
                self._connection.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (1)")
                self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def add_session(self, session: Session) -> None:
        with self._connection:
            self._connection.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session.id, session.title, session.started_at, session.duration_ms, session.media_path,
                 session.notes, int(session.is_demo), session.created_at))

    def get_session(self, session_id: str) -> Session | None:
        row = self._connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return Session(id=row["id"], title=row["title"], started_at=row["started_at"],
            duration_ms=row["duration_ms"], media_path=row["media_path"], notes=row["notes"],
            is_demo=bool(row["is_demo"]), created_at=row["created_at"])

    def list_sessions(self, *, include_demo: bool = False) -> list[Session]:
        sql = "SELECT * FROM sessions" if include_demo else "SELECT * FROM sessions WHERE is_demo = 0"
        rows = self._connection.execute(sql + " ORDER BY started_at DESC").fetchall()
        return [Session(id=r["id"], title=r["title"], started_at=r["started_at"],
            duration_ms=r["duration_ms"], media_path=r["media_path"], notes=r["notes"],
            is_demo=bool(r["is_demo"]), created_at=r["created_at"]) for r in rows]

    def add_observation(self, observation: Observation) -> None:
        parent = self.get_session(observation.session_id)
        if parent is None:
            raise ValueError("Observation session does not exist")
        if parent.is_demo != observation.is_demo:
            raise ValueError("Observation and parent session must share demo provenance")
        if parent.duration_ms is not None and observation.timestamp_ms > parent.duration_ms:
            raise ValueError("Observation timestamp exceeds session duration")
        with self._connection:
            self._connection.execute("INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (observation.id, observation.session_id, observation.timestamp_ms, observation.text,
                 observation.kind.value, json.dumps(list(observation.tags)), observation.created_at,
                 int(observation.is_demo)))

    def list_observations(self, session_id: str, *, include_demo: bool = False) -> list[Observation]:
        sql = "SELECT * FROM observations WHERE session_id = ?"
        args: list[Any] = [session_id]
        if not include_demo:
            sql += " AND is_demo = 0"
        rows = self._connection.execute(sql + " ORDER BY timestamp_ms", args).fetchall()
        return [Observation(id=r["id"], session_id=r["session_id"], timestamp_ms=r["timestamp_ms"],
            text=r["text"], kind=ObservationKind(r["kind"]), tags=tuple(json.loads(r["tags_json"])),
            created_at=r["created_at"], is_demo=bool(r["is_demo"])) for r in rows]

    def add_metric(self, metric: MetricResult) -> None:
        if metric.session_id is not None:
            parent = self.get_session(metric.session_id)
            if parent is None:
                raise ValueError("Metric session does not exist")
            if parent.is_demo != metric.is_demo:
                raise ValueError("Metric and parent session must share demo provenance")
        with self._connection:
            self._connection.execute("INSERT INTO metric_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (metric.id, metric.session_id, metric.name, metric.unit, metric.source, metric.method,
                 metric.value, metric.validity, metric.confidence, metric.notes, int(metric.is_demo), metric.measured_at))

    def list_metrics(self, *, session_id: str | None = None, include_demo: bool = False) -> list[MetricResult]:
        clauses: list[str] = []
        args: list[Any] = []
        if not include_demo:
            clauses.append("is_demo = 0")
        if session_id is not None:
            clauses.append("session_id = ?")
            args.append(session_id)
        sql = "SELECT * FROM metric_results" + (" WHERE " + " AND ".join(clauses) if clauses else "")
        rows = self._connection.execute(sql + " ORDER BY measured_at DESC", args).fetchall()
        return [MetricResult(id=r["id"], session_id=r["session_id"], name=r["name"], unit=r["unit"],
            source=r["source"], method=r["method"], value=r["value"], validity=r["validity"],
            confidence=r["confidence"], notes=r["notes"], is_demo=bool(r["is_demo"]),
            measured_at=r["measured_at"]) for r in rows]

    def add_settings_snapshot(self, snapshot: SettingsSnapshot) -> None:
        with self._connection:
            self._connection.execute("INSERT INTO settings_snapshots VALUES (?, ?, ?, ?, ?)",
                (snapshot.id, snapshot.label, json.dumps(snapshot.values, sort_keys=True),
                 snapshot.created_at, int(snapshot.is_demo)))

    def add_experiment(self, experiment: SettingsExperiment) -> None:
        baseline = self._connection.execute("SELECT is_demo FROM settings_snapshots WHERE id = ?",
            (experiment.baseline_snapshot_id,)).fetchone()
        if baseline is None:
            raise ValueError("Baseline settings snapshot does not exist")
        if bool(baseline["is_demo"]) != experiment.is_demo:
            raise ValueError("Experiment and baseline snapshot must share demo provenance")
        if experiment.test_snapshot_id is not None:
            test = self._connection.execute("SELECT is_demo FROM settings_snapshots WHERE id = ?",
                (experiment.test_snapshot_id,)).fetchone()
            if test is None:
                raise ValueError("Test settings snapshot does not exist")
            if bool(test["is_demo"]) != experiment.is_demo:
                raise ValueError("Experiment and test snapshot must share demo provenance")
        with self._connection:
            self._connection.execute("INSERT INTO settings_experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (experiment.id, experiment.title, experiment.hypothesis, experiment.baseline_snapshot_id,
                 experiment.changed_variable, experiment.test_snapshot_id, experiment.outcome, experiment.notes,
                 experiment.status, experiment.created_at, int(experiment.is_demo)))

    def list_experiments(self, *, include_demo: bool = False) -> list[SettingsExperiment]:
        sql = "SELECT * FROM settings_experiments" if include_demo else "SELECT * FROM settings_experiments WHERE is_demo = 0"
        rows = self._connection.execute(sql + " ORDER BY created_at DESC").fetchall()
        return [SettingsExperiment(id=r["id"], title=r["title"], hypothesis=r["hypothesis"],
            baseline_snapshot_id=r["baseline_snapshot_id"], changed_variable=r["changed_variable"],
            test_snapshot_id=r["test_snapshot_id"], outcome=r["outcome"], notes=r["notes"],
            status=r["status"], created_at=r["created_at"], is_demo=bool(r["is_demo"])) for r in rows]
