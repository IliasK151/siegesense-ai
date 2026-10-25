"""Tests for settings snapshots and experiment provenance."""

import pytest

from siegesense.domain.models import SettingsExperiment, SettingsSnapshot
from siegesense.storage.database import Database


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    yield database
    database.close()


def test_settings_snapshot_round_trip_is_deterministic(db: Database) -> None:
    snapshot = SettingsSnapshot(
        id="baseline",
        label="Baseline",
        values={"vertical": 6, "horizontal": 6, "scopes": {"1x": 40, "2.5x": 44}},
    )
    db.add_settings_snapshot(snapshot)

    assert db.get_settings_snapshot("baseline") == snapshot
    assert db.list_settings_snapshots() == [snapshot]


def test_demo_settings_are_hidden_by_default(db: Database) -> None:
    db.add_settings_snapshot(SettingsSnapshot(id="real", values={"sens": 6}))
    db.add_settings_snapshot(SettingsSnapshot(id="demo", values={"sens": 9}, is_demo=True))

    assert [item.id for item in db.list_settings_snapshots()] == ["real"]
    assert {item.id for item in db.list_settings_snapshots(include_demo=True)} == {"real", "demo"}


def test_settings_snapshot_rejects_non_finite_numbers(db: Database) -> None:
    db.add_settings_snapshot(SettingsSnapshot(id="baseline", values={"sens": 6}))
    with pytest.raises(ValueError, match="JSON compliant"):
        db.add_settings_snapshot(SettingsSnapshot(id="bad", values={"sens": float("nan")}))
    assert [item.id for item in db.list_settings_snapshots()] == ["baseline"]


def test_experiment_can_reference_matching_baseline_and_test(db: Database) -> None:
    baseline = SettingsSnapshot(id="baseline", values={"sens": 6})
    test = SettingsSnapshot(id="test", values={"sens": 5})
    db.add_settings_snapshot(baseline)
    db.add_settings_snapshot(test)
    experiment = SettingsExperiment(
        id="experiment",
        title="One-variable comparison",
        hypothesis="A small change may feel more controllable",
        baseline_snapshot_id="baseline",
        test_snapshot_id="test",
        changed_variable="horizontal sensitivity",
        status="completed",
        outcome="inconclusive",
    )
    db.add_experiment(experiment)

    assert db.list_experiments() == [experiment]


def test_experiment_rejects_demo_test_snapshot_for_real_baseline(db: Database) -> None:
    db.add_settings_snapshot(SettingsSnapshot(id="baseline", values={"sens": 6}))
    db.add_settings_snapshot(SettingsSnapshot(id="demo-test", values={"sens": 5}, is_demo=True))
    experiment = SettingsExperiment(
        title="Mixed provenance",
        hypothesis="Never mix demo and real records",
        baseline_snapshot_id="baseline",
        test_snapshot_id="demo-test",
    )

    with pytest.raises(ValueError, match="provenance"):
        db.add_experiment(experiment)
