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
        assert "1 setting change(s)" in window.settings_experiment_list.item(0).text()
        comparison = window.settings_comparison_label.text()
        assert "Horizontal: 6 → 5" in comparison
        assert "1 setting(s) differ" in comparison

        window.experiment_status_combo.setCurrentIndex(
            window.experiment_status_combo.findData("completed")
        )
        window.experiment_outcome_input.setText("Slightly easier to stop on target in two review clips")
        window._update_selected_experiment()
        assert "1 completed" in window.experiment_history_summary.text()
        assert "Slightly easier to stop on target" in window.experiment_history_summary.text()
        assert "not proof" in window.experiment_history_summary.text()
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



def test_settings_lab_rejects_multiple_setting_changes(app: QApplication, monkeypatch) -> None:
    database = Database(":memory:")
    service = SettingsService(database)
    baseline = service.save_snapshot("Baseline", {"horizontal": 6, "vertical": 6})
    test = service.save_snapshot("Test", {"horizontal": 5, "vertical": 5})
    window = MainWindow(settings_service=service)
    try:
        window.experiment_baseline_combo.setCurrentIndex(
            window.experiment_baseline_combo.findData(baseline.id)
        )
        window.experiment_test_combo.setCurrentIndex(
            window.experiment_test_combo.findData(test.id)
        )
        window.experiment_title_input.setText("Confounded sensitivity test")
        window.experiment_hypothesis_input.setText("One change may help")
        window.experiment_variable_input.setText("horizontal sensitivity")
        messages: list[str] = []
        monkeypatch.setattr(
            "siegesense.ui.shell.QMessageBox.warning",
            lambda *args: messages.append(str(args[2])),
        )

        window._create_settings_experiment()

        assert service.list_experiments() == []
        assert messages and "exactly one changed setting" in messages[0]
    finally:
        window.close()
        database.close()



def test_settings_lab_records_dpi_and_mouse_sensitivity_multiplier(app: QApplication) -> None:
    database = Database(":memory:")
    service = SettingsService(database)
    window = MainWindow(settings_service=service)
    try:
        window.settings_label_input.setText("Verified baseline")
        window.settings_spinboxes["mouse_dpi"].setValue(800)
        window.settings_spinboxes["sensitivity_multiplier"].setValue(0.02)
        window._save_settings_snapshot()

        snapshot = service.list_snapshots()[0]
        assert snapshot.values["mouse_dpi"] == 800
        assert snapshot.values["sensitivity_multiplier"] == pytest.approx(0.02)
        assert snapshot.values["horizontal"] == 6
        assert snapshot.values["ads_2_5x"] == 44
    finally:
        window.close()
        database.close()
