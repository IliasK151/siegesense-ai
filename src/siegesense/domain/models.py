"""Typed records for sessions, observations, metrics, and settings experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    """Return an aware UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    """Generate a stable unique identifier."""
    return str(uuid4())


class ObservationKind(StrEnum):
    AIM = "aim"
    MOVEMENT = "movement"
    POSITIONING = "positioning"
    DECISION = "decision"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Session:
    id: str = field(default_factory=new_id)
    title: str = "Untitled session"
    started_at: str = field(default_factory=utc_now_iso)
    duration_ms: int | None = None
    media_path: str | None = None
    notes: str = ""
    is_demo: bool = False
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Session id must not be empty")
        if not self.title.strip():
            raise ValueError("Session title must not be empty")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("Session duration cannot be negative")


@dataclass(frozen=True, slots=True)
class Observation:
    session_id: str
    timestamp_ms: int
    text: str
    kind: ObservationKind = ObservationKind.OTHER
    id: str = field(default_factory=new_id)
    tags: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now_iso)
    is_demo: bool = False

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("Observation must belong to a session")
        if self.timestamp_ms < 0:
            raise ValueError("Observation timestamp cannot be negative")
        if not self.text.strip():
            raise ValueError("Observation text must not be empty")
        if not self.id.strip():
            raise ValueError("Observation id must not be empty")
        if any(not tag.strip() for tag in self.tags):
            raise ValueError("Observation tags must not be empty strings")


@dataclass(frozen=True, slots=True)
class MetricResult:
    name: str
    unit: str
    source: str
    method: str
    value: float | None
    validity: str
    id: str = field(default_factory=new_id)
    session_id: str | None = None
    confidence: float | None = None
    notes: str = ""
    is_demo: bool = False
    measured_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        for label, value in (("name", self.name), ("unit", self.unit), ("source", self.source), ("method", self.method), ("validity", self.validity)):
            if not value.strip():
                raise ValueError(f"Metric {label} must not be empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Metric confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SettingsSnapshot:
    values: dict[str, Any]
    id: str = field(default_factory=new_id)
    label: str = "Settings snapshot"
    created_at: str = field(default_factory=utc_now_iso)
    is_demo: bool = False

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("Settings snapshot label must not be empty")


@dataclass(frozen=True, slots=True)
class SettingsExperiment:
    title: str
    hypothesis: str
    baseline_snapshot_id: str
    id: str = field(default_factory=new_id)
    changed_variable: str = ""
    test_snapshot_id: str | None = None
    outcome: str | None = None
    notes: str = ""
    status: str = "planned"
    created_at: str = field(default_factory=utc_now_iso)
    is_demo: bool = False

    def __post_init__(self) -> None:
        for label, value in (("title", self.title), ("hypothesis", self.hypothesis), ("baseline_snapshot_id", self.baseline_snapshot_id)):
            if not value.strip():
                raise ValueError(f"Experiment {label} must not be empty")
        if self.status not in {"planned", "running", "completed", "inconclusive", "cancelled"}:
            raise ValueError("Experiment status is not supported")
