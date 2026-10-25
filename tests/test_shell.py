"""Smoke tests for the initial desktop shell."""

from PySide6.QtWidgets import QApplication

from siegesense.ui.shell import NAV_ITEMS, MainWindow


def _application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_shell_contains_all_planned_destinations() -> None:
    _application()
    window = MainWindow()
    assert window.page_stack.count() == len(NAV_ITEMS) == 7
    window.close()


def test_navigation_updates_selected_page_and_breadcrumb() -> None:
    _application()
    window = MainWindow()

    window.show_page("Settings Lab")

    assert window.page_stack.currentIndex() == 3
    assert window.breadcrumb.text() == "Workspace  /  Settings Lab"
    assert window._nav_buttons["Settings Lab"].property("active") is True
    assert window._nav_buttons["Overview"].property("active") is False
    window.close()
