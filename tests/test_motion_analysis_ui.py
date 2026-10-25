"""UI integration test for exporting a local screen-space motion report."""
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_annotation_lab_exports_motion_report_locally(
    app: QApplication, tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "sampling_manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    output = tmp_path / "motion.json"
    database = Database(":memory:")
    window = MainWindow()
    window._annotation_manifest_path = manifest
    try:
        monkeypatch.setattr(
            "siegesense.ui.shell.QFileDialog.getSaveFileName",
            lambda *args: (str(output), "JSON report (*.json)"),
        )
        monkeypatch.setattr(
            "siegesense.ui.shell.analyze_manifest_motion",
            lambda path: SimpleNamespace(
                median_motion_px_per_sample=2.0,
                p90_motion_px_per_sample=4.0,
                pairs=(SimpleNamespace(coherent_feature_ratio=0.75),),
            ),
        )
        monkeypatch.setattr(
            "siegesense.ui.shell.write_motion_report",
            lambda report, path: Path(path),
        )

        window._analyze_annotation_motion()

        assert "Median visible-feature motion: 2.00" in window.annotation_status.text()
        assert "not mouse input" in window.annotation_status.text()
        assert "coherent-feature ratio: 75%" in window.annotation_status.text()
    finally:
        window.close()
        database.close()
