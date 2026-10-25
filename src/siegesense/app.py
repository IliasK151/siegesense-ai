"""Application bootstrap and top-level dependency wiring."""

from __future__ import annotations

import sqlite3
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from siegesense.services.session_service import SessionService
from siegesense.services.settings_service import SettingsService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow
from siegesense.ui.theme import APP_STYLESHEET


def main() -> int:
    """Create the desktop application and manage its local database lifecycle."""
    app = QApplication(sys.argv)
    app.setApplicationName("SiegeSense AI")
    app.setOrganizationName("SiegeSense")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    try:
        database = Database()
    except (OSError, sqlite3.Error, RuntimeError) as error:
        QMessageBox.critical(
            None,
            "Unable to open local data",
            "SiegeSense AI could not open its local database. No session data was changed.\n\n"
            f"Details: {error}",
        )
        return 1

    app.aboutToQuit.connect(database.close)
    session_service = SessionService(database)
    window = MainWindow(
        session_service=session_service,
        settings_service=SettingsService(database),
    )
    window.show()
    return app.exec()
