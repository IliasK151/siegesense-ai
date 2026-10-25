"""Tests for full-frame normalized coordinates in the manual point picker."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from siegesense.ui.point_picker import PointPickerLabel


@pytest.fixture
def app() -> QApplication:
    instance = QApplication.instance()
    return instance if instance is not None else QApplication([])


def test_click_maps_to_source_coordinates_with_letterboxing(app: QApplication) -> None:
    image = QPixmap(320, 180)
    image.fill(Qt.GlobalColor.darkBlue)
    picker = PointPickerLabel()
    picker.resize(400, 300)
    picker.set_source_pixmap(image)
    picker.show()
    app.processEvents()
    try:
        rect = picker.displayed_image_rect()
        assert rect.width() == pytest.approx(400)
        assert rect.height() == pytest.approx(225)
        assert rect.y() > 0  # The 16:9 image is letterboxed vertically.

        picker.set_marking_mode("reticle")
        # Click in the top letterbox: it must not become an image coordinate.
        QTest.mouseClick(picker, Qt.MouseButton.LeftButton, pos=QPoint(200, 10))
        assert picker.point_coordinates()["reticle_x"] is None
        assert picker.marking_mode == "reticle"

        # A click one quarter of the way across and halfway down the image.
        QTest.mouseClick(
            picker,
            Qt.MouseButton.LeftButton,
            pos=QPoint(round(rect.x() + rect.width() * 0.25),
                       round(rect.y() + rect.height() * 0.5)),
        )
        coords = picker.point_coordinates()
        assert coords["reticle_x"] == pytest.approx(0.25, abs=0.01)
        assert coords["reticle_y"] == pytest.approx(0.5, abs=0.01)
        assert picker.marking_mode is None

        picker.set_marking_mode("target")
        QTest.mouseClick(
            picker,
            Qt.MouseButton.LeftButton,
            pos=QPoint(round(rect.x() + rect.width() * 0.75),
                       round(rect.y() + rect.height() * 0.5)),
        )
        coords = picker.point_coordinates()
        assert coords["target_x"] == pytest.approx(0.75, abs=0.01)
        assert coords["target_y"] == pytest.approx(0.5, abs=0.01)
    finally:
        picker.close()


def test_point_coordinates_validate_normalized_range(app: QApplication) -> None:
    picker = PointPickerLabel()
    with pytest.raises(ValueError, match="between 0 and 1"):
        picker.set_points((1.1, 0.5), None)



def test_unavailable_image_clears_stale_points(app: QApplication) -> None:
    image = QPixmap(100, 100)
    picker = PointPickerLabel()
    picker.set_source_pixmap(image)
    picker.set_points((0.2, 0.3), (0.7, 0.8))
    picker.set_image_message("Image unavailable")
    assert picker.point_coordinates() == {
        "reticle_x": None, "reticle_y": None, "target_x": None, "target_y": None,
    }
    assert picker.pixmap().isNull()
    assert picker.text() == "Image unavailable"
