"""Smoke tests for the initial desktop shell."""

from PySide6.QtWidgets import QApplication, QScrollArea

from siegesense.ui.shell import NAV_ITEMS, MainWindow


def _application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_shell_contains_all_planned_destinations() -> None:
    _application()
    window = MainWindow()
    try:
        assert window.page_stack.count() == len(NAV_ITEMS) == 8
        assert "Clip Annotation" in window._nav_buttons
        assert all(
            isinstance(window.page_stack.widget(index), QScrollArea)
            for index in range(window.page_stack.count())
        )
        assert set(window.overview_action_buttons) == {
            "Session Review", "Clip Annotation", "Settings Lab", "AI Coach"
        }
    finally:
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


def test_data_mode_badge_does_not_mislabel_real_records_as_demo() -> None:
    _application()
    window = MainWindow()
    try:
        assert window.data_mode_badge.text() == "LOCAL DATA · DEMO RECORDS HIDDEN"
        assert "DEMO MODE" not in window.data_mode_badge.text()
    finally:
        window.close()



def test_overview_quick_action_opens_the_requested_workspace() -> None:
    _application()
    window = MainWindow()
    try:
        window.overview_action_buttons["Clip Annotation"].click()
        assert window.breadcrumb.text() == "Workspace  /  Clip Annotation"
        assert window.page_stack.currentIndex() == 5
    finally:
        window.close()
