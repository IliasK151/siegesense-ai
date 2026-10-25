"""Application bootstrap and top-level dependency wiring."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from siegesense.ui.shell import MainWindow
from siegesense.ui.theme import APP_STYLESHEET


def main() -> int:
    """Create and run the desktop application."""
    app = QApplication(sys.argv)
    app.setApplicationName("SiegeSense AI")
    app.setOrganizationName("SiegeSense")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()
