import math

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.gesture_assistant.ui import tokens
from src.gesture_assistant.ui.theme import NO_PREVIEW_TEXT
from src.gesture_assistant.vision.hand_provider import Hand, HandPoint

HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
)


class CameraView(QWidget):
    """Podgląd obrazu z zachowaniem proporcji oraz rysowanie szkieletu."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Podgląd kamery")
        self._image: QImage | None = None
        self._hands: tuple[Hand, ...] = ()

    def set_frame(self, frame_bgr: np.ndarray, hands: tuple[Hand, ...]) -> None:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        self._image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        ).copy()
        self._hands = hands
        self.update()

    def clear(self) -> None:
        self._image = None
        self._hands = ()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(tokens.BACKGROUND))

        if self._image is None:
            painter.setPen(QPen(QColor(tokens.SECONDARY)))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, NO_PREVIEW_TEXT)
            return

        target = self._scaled_target_rect(self._image.size())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target, self._image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.save()
        painter.setClipRect(target)
        for hand in self._hands:
            if len(hand.landmarks) == 21 and all(
                math.isfinite(value)
                for point in hand.landmarks
                for value in (point.x, point.y, point.z)
            ):
                self._draw_skeleton(painter, target, hand)
        painter.restore()

    def _scaled_target_rect(self, image_size) -> QRect:
        widget_width = self.width()
        widget_height = self.height()
        image_width = image_size.width()
        image_height = image_size.height()

        scale = min(widget_width / image_width, widget_height / image_height)
        target_width = int(image_width * scale)
        target_height = int(image_height * scale)
        x = (widget_width - target_width) // 2
        y = (widget_height - target_height) // 2

        return QRect(x, y, target_width, target_height)

    def _draw_skeleton(self, painter: QPainter, target: QRect, hand: Hand) -> None:
        landmarks = hand.landmarks

        painter.setPen(QPen(QColor(tokens.ACCENT), 3))

        for first_index, second_index in HAND_CONNECTIONS:
            if first_index >= len(landmarks) or second_index >= len(landmarks):
                continue

            first = self._map_landmark(landmarks[first_index], target)
            second = self._map_landmark(landmarks[second_index], target)
            painter.drawLine(first, second)

        painter.setPen(QPen(QColor(tokens.TEXT), 1))
        painter.setBrush(QColor(tokens.TEXT))

        for landmark in landmarks:
            point = self._map_landmark(landmark, target)
            painter.drawEllipse(point, 3, 3)

    def _map_landmark(self, landmark: HandPoint, target: QRect) -> QPoint:
        x = target.x() + int(max(-1.0, min(2.0, landmark.x)) * target.width())
        y = target.y() + int(max(-1.0, min(2.0, landmark.y)) * target.height())
        return QPoint(x, y)

