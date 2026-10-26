"""UI integration test for exporting a manual spatial-offset report."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from siegesense.ui.shell import MainWindow
from siegesense.vision.annotations import AnnotationStore


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_annotation_workspace_exports_manual_spatial_report(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "sampling_manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "source_sha256": "spatial-ui-source",
        "interval_ms": 100,
        "frames": [{"timestamp_ms": 0, "filename": "frame0.png"}],
    }), encoding="utf-8")
    dataset_path = tmp_path / "annotations.json"
    store = AnnotationStore(manifest, dataset_path)
    store.add(
        0, "frame0.png", "crosshair_off_target", annotator="reviewer",
        reticle_x=0.5, reticle_y=0.5, target_x=0.7, target_y=0.4,
    )
    output = tmp_path / "spatial-offset-report.json"
    window = MainWindow()
    try:
        window._annotation_store = store
        monkeypatch.setattr(
            "siegesense.ui.shell.QFileDialog.getSaveFileName",
            lambda *_args, **_kwargs: (str(output), "JSON report (*.json)"),
        )

        window._export_spatial_report()

        assert output.is_file()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["summary"]["annotated_point_count"] == 1
        assert report["observations"][0]["horizontal_offset_pct"] == 20.0
        assert "not aim accuracy" in window.annotation_status.text()
    finally:
        window.close()
