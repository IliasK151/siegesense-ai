"""Tests for local-data visibility and database backups in Preferences & Privacy."""

import sqlite3

from PySide6.QtWidgets import QApplication

from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow


def _application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_preferences_show_storage_and_export_consistent_database_backup(tmp_path, monkeypatch) -> None:
    _application()
    database_path = tmp_path / "local-data" / "siegesense.sqlite3"
    with Database(database_path) as database:
        service = SessionService(database)
        service.create_session("Backup proof")
        window = MainWindow(session_service=service, database_path=database_path)
        backup_path = tmp_path / "exports" / "siegesense-backup.sqlite3"
        backup_path.parent.mkdir()
        monkeypatch.setattr(
            "siegesense.ui.shell.QFileDialog.getSaveFileName",
            lambda *args: (str(backup_path), "SQLite database (*.sqlite3 *.db)"),
        )
        try:
            assert str(database_path) in window.storage_path_label.text()
            assert "Existing local database" in window.storage_status_label.text()
            window._export_database_backup()
            assert backup_path.is_file()
            with sqlite3.connect(backup_path) as backup:
                row = backup.execute("SELECT title FROM sessions").fetchone()
            assert row == ("Backup proof",)
            assert str(backup_path) in window.storage_status_label.text()
        finally:
            window.close()
