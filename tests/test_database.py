"""Persistence tests use isolated in-memory SQLite databases."""

import pytest

from siegesense.domain.models import MetricResult, Observation, ObservationKind, Session, SettingsExperiment, SettingsSnapshot
from siegesense.storage.database import Database, SCHEMA_VERSION


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    yield database
    database.close()


def test_schema_is_versioned(db: Database) -> None:
    version = db._connection.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION == 1


def test_sessions_round_trip_and_demo_filter(db: Database) -> None:
    real = Session(id="real", title="Ranked review")
    demo = Session(id="demo", title="Example", is_demo=True)
    db.add_session(real)
    db.add_session(demo)
    assert [item.id for item in db.list_sessions()] == ["real"]
    assert {item.id for item in db.list_sessions(include_demo=True)} == {"real", "demo"}
    assert db.get_session("real").title == "Ranked review"


def test_observation_round_trip_keeps_tags_and_order(db: Database) -> None:
    db.add_session(Session(id="s", duration_ms=5000))
    later = Observation(session_id="s", timestamp_ms=2000, text="late peek", kind=ObservationKind.MOVEMENT, tags=("peek", "timing"))
    earlier = Observation(session_id="s", timestamp_ms=1000, text="crosshair too low")
    db.add_observation(later)
    db.add_observation(earlier)
    result = db.list_observations("s")
    assert [item.timestamp_ms for item in result] == [1000, 2000]
    assert result[1].tags == ("peek", "timing")


def test_observation_cannot_mix_demo_provenance(db: Database) -> None:
    db.add_session(Session(id="demo", is_demo=True))
    with pytest.raises(ValueError, match="provenance"):
        db.add_observation(Observation(session_id="demo", timestamp_ms=0, text="example", is_demo=False))


def test_observation_must_fit_known_session_duration(db: Database) -> None:
    db.add_session(Session(id="s", duration_ms=1000))
    with pytest.raises(ValueError, match="exceeds"):
        db.add_observation(Observation(session_id="s", timestamp_ms=1001, text="outside clip"))


def test_missing_metric_value_round_trips_as_none(db: Database) -> None:
    db.add_session(Session(id="s"))
    db.add_metric(MetricResult(session_id="s", name="flick deviation", unit="px", source="recording", method="not yet measured", value=None, validity="missing"))
    assert db.list_metrics()[0].value is None


def test_metric_demo_provenance_must_match_parent(db: Database) -> None:
    db.add_session(Session(id="s", is_demo=False))
    with pytest.raises(ValueError, match="provenance"):
        db.add_metric(MetricResult(session_id="s", name="example", unit="px", source="demo", method="synthetic", value=2, validity="demo", is_demo=True))


def test_experiment_requires_existing_matching_baseline(db: Database) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        db.add_experiment(SettingsExperiment(title="Test", hypothesis="Try a change", baseline_snapshot_id="missing"))
    baseline = SettingsSnapshot(id="baseline", values={"horizontal": 6})
    db.add_settings_snapshot(baseline)
    db.add_experiment(SettingsExperiment(title="Test", hypothesis="Try a change", baseline_snapshot_id="baseline"))
    assert len(db.list_experiments()) == 1


def test_demo_experiment_cannot_use_real_snapshot(db: Database) -> None:
    db.add_settings_snapshot(SettingsSnapshot(id="real", values={"sens": 6}))
    with pytest.raises(ValueError, match="provenance"):
        db.add_experiment(SettingsExperiment(title="Example", hypothesis="Demo only", baseline_snapshot_id="real", is_demo=True))
