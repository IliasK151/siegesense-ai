"""Application bootstrap and top-level dependency wiring."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from siegesense.services.session_service import SessionService
from siegesense.services.settings_service import SettingsService
from siegesense.storage.database import Database
from siegesense.ui.shell import MainWindow
from siegesense.ui.theme import APP_STYLESHEET


def _write_smoke_failure() -> None:
    """Persist smoke-test tracebacks where a windowed executable has no console."""
    log_path = Path(
        os.environ.get(
            "SIEGESENSE_SMOKE_LOG",
            str(Path(tempfile.gettempdir()) / "siegesense-smoke-test-error.txt"),
        )
    )
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        # Preserve the original non-zero smoke-test exit if diagnostics cannot be written.
        pass


def _run_application(smoke_test: bool) -> int:
    """Initialize Qt, local services, and either smoke-test or show the window."""
    qt_args = [argument for argument in sys.argv if argument != "--smoke-test"]
    app = QApplication(qt_args)
    app.setApplicationName("SiegeSense AI")
    app.setOrganizationName("SiegeSense")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    try:
        database = Database()
    except (OSError, sqlite3.Error, RuntimeError) as error:
        if smoke_test:
            raise RuntimeError(f"Unable to initialize local database: {error}") from error
        QMessageBox.critical(
            None,
            "Unable to open local data",
            "SiegeSense AI could not open its local database. No session data was changed.\n\n"
            f"Details: {error}",
        )
        return 1

    try:
        session_service = SessionService(database)
        window = MainWindow(
            session_service=session_service,
            settings_service=SettingsService(database),
        )
        if smoke_test:
            expected_pages = {
                "Overview",
                "Aim Lab",
                "Movement",
                "Settings Lab",
                "Session Review",
                "Clip Annotation",
                "AI Coach",
                "Preferences & Privacy",
            }
            if set(window._nav_buttons) != expected_pages:
                raise RuntimeError("Desktop navigation smoke test failed")
            if window.page_stack.count() != len(expected_pages):
                raise RuntimeError("Desktop page-stack smoke test failed")
            window.close()
            return 0

        window.show()
        return app.exec()
    finally:
        database.close()


def main() -> int:
    """Run the app and preserve diagnostics for packaged smoke-test failures."""
    smoke_test = "--smoke-test" in sys.argv
    try:
        return _run_application(smoke_test)
    except Exception:
        if smoke_test:
            _write_smoke_failure()
            return 1
        raise
