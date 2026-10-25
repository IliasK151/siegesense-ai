"""Aspect-ratio-safe frame viewer with optional manual reticle/target point marking."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel


class PointPickerLabel(QLabel):
    """Display a full frame and map user clicks to normalized source-image coordinates.

    The QLabel's letterboxed area is deliberately not clickable: returned coordinates
    always refer to the displayed source image, not the surrounding widget.
    """

    point_marked = Signal(str, float, float)

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._source_pixmap = QPixmap()
        self._marking_mode: str | None = None
        self._reticle_point: tuple[float, float] | None = None
        self._target_point: tuple[float, float] | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)

    def set_source_pixmap(self, pixmap: QPixmap) -> None:
        """Set the original frame image; scaling is recalculated on resize."""
        self._source_pixmap = QPixmap(pixmap)
        if self._source_pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText("This image could not be decoded.")
        else:
            self.setText("")
            self._refresh_display_pixmap()
        self.update()

    def set_image_message(self, message: str) -> None:
        """Clear the image and present an explanatory message."""
        self._source_pixmap = QPixmap()
        self.setPixmap(QPixmap())
        self._marking_mode = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setText(message)
        self.update()

    def set_marking_mode(self, mode: str | None) -> None:
        """Arm a one-click mark operation for the reticle or target."""
        if mode not in (None, "reticle", "target"):
            raise ValueError("Marking mode must be 'reticle', 'target', or None")
        if mode is not None and self._source_pixmap.isNull():
            raise ValueError("Load a readable frame before marking points")
        self._marking_mode = mode
        self.setCursor(
            Qt.CursorShape.CrossCursor if mode is not None else Qt.CursorShape.ArrowCursor
        )

    @property
    def marking_mode(self) -> str | None:
        return self._marking_mode

    def set_points(
        self,
        reticle: tuple[float, float] | None,
        target: tuple[float, float] | None,
    ) -> None:
        """Restore saved normalized point coordinates and redraw their markers."""
        self._reticle_point = self._validate_point(reticle)
        self._target_point = self._validate_point(target)
        self.set_marking_mode(None)
        self.update()

    def clear_points(self) -> None:
        """Remove both unsaved or displayed point markers."""
        self._reticle_point = None
        self._target_point = None
        self.set_marking_mode(None)
        self.update()

    def point_coordinates(self) -> dict[str, float | None]:
        """Return coordinate fields compatible with AnnotationStore.add/update."""
        return {
            "reticle_x": None if self._reticle_point is None else self._reticle_point[0],
            "reticle_y": None if self._reticle_point is None else self._reticle_point[1],
            "target_x": None if self._target_point is None else self._target_point[0],
            "target_y": None if self._target_point is None else self._target_point[1],
        }

    @staticmethod
    def _validate_point(point: tuple[float, float] | None) -> tuple[float, float] | None:
        if point is None:
            return None
        x, y = point
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError("Point coordinates must be normalized between 0 and 1")
        return float(x), float(y)

    def displayed_image_rect(self) -> QRectF:
        """Return the actual letterboxed image rectangle in widget coordinates."""
        displayed = self.pixmap()
        if displayed is None or displayed.isNull():
            return QRectF()
        content = self.contentsRect()
        x = content.x() + (content.width() - displayed.width()) / 2
        y = content.y() + (content.height() - displayed.height()) / 2
        return QRectF(x, y, displayed.width(), displayed.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_display_pixmap()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        mode = self._marking_mode
        if mode is None or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        image_rect = self.displayed_image_rect()
        position = event.position()
        if image_rect.isEmpty() or not image_rect.contains(position):
            # A click in the surrounding letterbox is not a point on the recording.
            event.accept()
            return
        x = min(1.0, max(0.0, (position.x() - image_rect.x()) / image_rect.width()))
        y = min(1.0, max(0.0, (position.y() - image_rect.y()) / image_rect.height()))
        point = (round(x, 6), round(y, 6))
        if mode == "reticle":
            self._reticle_point = point
        else:
            self._target_point = point
        self.set_marking_mode(None)
        self.update()
        self.point_marked.emit(mode, point[0], point[1])
        event.accept()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        image_rect = self.displayed_image_rect()
        if image_rect.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for mode, point, color in (
            ("R", self._reticle_point, QColor("#36C9F0")),
            ("T", self._target_point, QColor("#FF647C")),
        ):
            if point is None:
                continue
            center = QPointF(
                image_rect.x() + point[0] * image_rect.width(),
                image_rect.y() + point[1] * image_rect.height(),
            )
            painter.setPen(QPen(QColor("#FFFFFF"), 3))
            painter.drawEllipse(center, 8, 8)
            painter.setPen(QPen(color, 2))
            painter.drawEllipse(center, 7, 7)
            painter.drawLine(QPointF(center.x() - 11, center.y()), QPointF(center.x() + 11, center.y()))
            painter.drawLine(QPointF(center.x(), center.y() - 11), QPointF(center.x(), center.y() + 11))
            painter.drawText(QPointF(center.x() + 10, center.y() - 9), mode)
        painter.end()

    def _refresh_display_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        content = self.contentsRect()
        if content.width() < 1 or content.height() < 1:
            return
        self.setPixmap(
            self._source_pixmap.scaled(
                content.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
