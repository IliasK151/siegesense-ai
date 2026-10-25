"""UI-level test for exporting a selected session review."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from siegesense.domain.models import ObservationKind
from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_session_review_exports_selected_session(app: QApplication, tmp_path: Path, monkeypatch) -> None:
    database = Database(":memory:")
    service = SessionService(database)
    session = service.create_session("Ranked match")
    service.add_observation(session.id, 83_000, "Overshot during target switch", kind=ObservationKind.AIM)
    target = tmp_path / "review.md"
    monkeypatch.setattr(
        "siegesense.ui.shell.QFileDialog.getSaveFileName",
        lambda *args: (str(target), "Markdown files (*.md)"),
    )
    window = MainWindow(session_service=service)
    try:
        window._export_session_summary()
        content = target.read_text(encoding="utf-8")
        assert "# Session review: Ranked match" in content
        assert "01:23 · Aim" in content
        assert "Overshot during target switch" in content
        assert str(target) in window.review_status.text()
    finally:
        window.close()
        database.close()



@pytest.mark.parametrize(
    ("suffix", "selected_filter", "expected"),
    [
        (".json", "Structured JSON (*.json)", '"timestamp_ms": 83000'),
        (".csv", "Observation CSV (*.csv)", "83000,01:23,aim"),
    ],
)
def test_session_review_exports_structured_formats(
    app: QApplication, tmp_path: Path, monkeypatch, suffix: str, selected_filter: str, expected: str
) -> None:
    database = Database(":memory:")
    service = SessionService(database)
    session = service.create_session("Structured export")
    service.add_observation(
        session.id, 83_000, "Overshot during target switch",
        kind=ObservationKind.AIM, tags=("overshoot", "acog"),
    )
    target = tmp_path / f"review{suffix}"
    monkeypatch.setattr(
        "siegesense.ui.shell.QFileDialog.getSaveFileName",
        lambda *args: (str(target), selected_filter),
    )
    window = MainWindow(session_service=service)
    try:
        window._export_session_summary()
        content = target.read_text(encoding="utf-8")
        assert expected in content
        assert "overshoot" in content
        assert str(target) in window.review_status.text()
    finally:
        window.close()
        database.close()
