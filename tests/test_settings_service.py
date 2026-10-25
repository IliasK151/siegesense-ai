"""Tests for the UI-independent settings workflow service."""

import pytest

from siegesense.services.settings_service import SettingsService
from siegesense.storage.database import Database


@pytest.fixture
def service() -> SettingsService:
    database = Database(":memory:")
    yield SettingsService(database)
    database.close()


def test_save_snapshot_and_create_experiment(service: SettingsService) -> None:
    baseline = service.save_snapshot("Baseline", {"horizontal": 6, "vertical": 6})
    changed = service.save_snapshot("Test A", {"horizontal": 5, "vertical": 6})
    experiment = service.create_experiment(
        "Single-variable test",
        "Compare one change at a time",
        baseline.id,
        changed_variable="horizontal sensitivity",
        test_snapshot_id=changed.id,
    )

    assert service.list_snapshots() == [changed, baseline]
    assert service.list_experiments() == [experiment]


def test_demo_snapshots_and_experiments_stay_isolated(service: SettingsService) -> None:
    real = service.save_snapshot("Real baseline", {"sens": 6})
    demo = service.save_snapshot("Demo baseline", {"sens": 8}, is_demo=True)
    service.create_experiment("Real test", "Real hypothesis", real.id)
    service.create_experiment("Demo test", "Demo hypothesis", demo.id, is_demo=True)

    assert [item.label for item in service.list_snapshots()] == ["Real baseline"]
    assert [item.title for item in service.list_experiments()] == ["Real test"]
    assert len(service.list_snapshots(include_demo=True)) == 2
    assert len(service.list_experiments(include_demo=True)) == 2


def test_service_rejects_missing_baseline(service: SettingsService) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        service.create_experiment("Missing", "Need a baseline", "unknown")


def test_service_rejects_cross_provenance_snapshot(service: SettingsService) -> None:
    baseline = service.save_snapshot("Real baseline", {"sens": 6})
    demo_test = service.save_snapshot("Demo test", {"sens": 7}, is_demo=True)
    with pytest.raises(ValueError, match="provenance"):
        service.create_experiment(
            "Invalid comparison", "Do not mix records", baseline.id, test_snapshot_id=demo_test.id
        )
