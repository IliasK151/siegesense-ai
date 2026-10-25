"""Tests for recording settings experiment outcomes from the desktop UI."""

import pytest
from PySide6.QtWidgets import QApplication

from siegesense.services.settings_service import SettingsService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_settings_lab_records_completed_experiment_outcome(app: QApplication) -> None:
    database = Database(":memory:")
    service = SettingsService(database)
    baseline = service.save_snapshot("Baseline", {"horizontal": 6})
    test = service.save_snapshot("Test A", {"horizontal": 5})
    experiment = service.create_experiment(
        "Sensitivity test", "One change may improve control", baseline.id,
        changed_variable="horizontal sensitivity", test_snapshot_id=test.id,
    )
    window = MainWindow(settings_service=service)
    try:
        assert window.settings_experiment_list.currentItem().data(256) == experiment.id
        window.experiment_status_combo.setCurrentIndex(
            window.experiment_status_combo.findData("completed")
        )
        window.experiment_outcome_input.setText("Fewer overshoots in three reviewed rounds; sample is small")
        window._update_selected_experiment()

        updated = service.list_experiments()[0]
        assert updated.id == experiment.id
        assert updated.status == "completed"
        assert updated.outcome == "Fewer overshoots in three reviewed rounds; sample is small"
        assert "Completed" in window.settings_experiment_list.item(0).text()
    finally:
        window.close()
        database.close()


def test_settings_lab_requires_outcome_for_completed_experiment(app: QApplication, monkeypatch) -> None:
    database = Database(":memory:")
    service = SettingsService(database)
    baseline = service.save_snapshot("Baseline", {"horizontal": 6})
    service.create_experiment("Test", "Check one change", baseline.id)
    window = MainWindow(settings_service=service)
    try:
        window.experiment_status_combo.setCurrentIndex(
            window.experiment_status_combo.findData("completed")
        )
        window.experiment_outcome_input.clear()
        messages: list[str] = []
        monkeypatch.setattr(
            "siegesense.ui.shell.QMessageBox.information",
            lambda *args: messages.append(str(args[2])),
        )
        window._update_selected_experiment()
        assert messages and "outcome" in messages[0].lower()
        assert service.list_experiments()[0].status == "planned"
    finally:
        window.close()
        database.close()
