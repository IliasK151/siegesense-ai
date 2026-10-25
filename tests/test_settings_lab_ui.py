"""Integration tests for the settings snapshot and experiment UI."""

import pytest
from PySide6.QtWidgets import QApplication

from siegesense.services.settings_service import SettingsService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_settings_lab_saves_snapshots_and_records_experiment(app: QApplication) -> None:
    database = Database(":memory:")
    window = MainWindow(settings_service=SettingsService(database))
    try:
        window.settings_label_input.setText("Baseline")
        window.settings_spinboxes["horizontal"].setValue(6)
        window.settings_spinboxes["vertical"].setValue(6)
        window._save_settings_snapshot()
        baseline = window.experiment_baseline_combo.currentData()
        assert baseline is not None

        window.settings_label_input.setText("Test A")
        window.settings_spinboxes["horizontal"].setValue(5)
        window._save_settings_snapshot()
        test_id = window.experiment_test_combo.currentData()
        assert test_id is not None and test_id != baseline
        window.experiment_baseline_combo.setCurrentIndex(
            window.experiment_baseline_combo.findData(baseline)
        )
        window.experiment_test_combo.setCurrentIndex(
            window.experiment_test_combo.findData(test_id)
        )
        window.experiment_title_input.setText("One-variable sensitivity test")
        window.experiment_hypothesis_input.setText("Lower horizontal sensitivity may reduce overshooting")
        window.experiment_variable_input.setText("horizontal sensitivity")
        window._create_settings_experiment()

        experiments = window.settings_service.list_experiments()
        assert len(experiments) == 1
        assert experiments[0].baseline_snapshot_id == baseline
        assert experiments[0].test_snapshot_id == test_id
        assert experiments[0].changed_variable == "horizontal sensitivity"
        assert window.settings_experiment_list.count() == 1
    finally:
        window.close()
        database.close()


def test_settings_lab_hides_demo_snapshots(app: QApplication) -> None:
    database = Database(":memory:")
    service = SettingsService(database)
    service.save_snapshot("Real baseline", {"horizontal": 6})
    service.save_snapshot("Demo snapshot", {"horizontal": 9}, is_demo=True)
    window = MainWindow(settings_service=service)
    try:
        labels = [window.experiment_baseline_combo.itemText(i) for i in range(window.experiment_baseline_combo.count())]
        assert labels == ["Real baseline"]
    finally:
        window.close()
        database.close()
