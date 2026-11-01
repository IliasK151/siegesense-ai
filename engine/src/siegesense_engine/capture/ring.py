"""The last N seconds of the screen, kept as small JPEGs in memory so deaths can be clipped."""

from __future__ import annotations

import threading
from collections import deque

import cv2
import numpy as np

from .frames import Frame


class FrameRing:
    def __init__(self, seconds: float = 15, fps: int = 30, width: int = 960, quality: int = 70):
        self.seconds = seconds
        self.width = width
        self._quality = quality
        self._frames: deque[tuple[float, bytes]] = deque()
        self._bytes = 0
        self._lock = threading.Lock()

    def _encode(self, image: np.ndarray) -> bytes:
        h, w = image.shape[:2]
        if w > self.width:
            image = cv2.resize(image, (self.width, round(h * self.width / w)), cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
        if not ok:
            raise ValueError("JPEG encode failed")
        return buf.tobytes()

    def add(self, frame: Frame) -> None:
        data = self._encode(frame.image)
        with self._lock:
            self._frames.append((frame.t, data))
            self._bytes += len(data)
            horizon = frame.t - self.seconds
            while self._frames and self._frames[0][0] < horizon:
                self._bytes -= len(self._frames.popleft()[1])

    def window(self, t_from: float, t_to: float) -> list[tuple[float, bytes]]:
        with self._lock:
            return [(t, d) for t, d in self._frames if t_from <= t <= t_to]

    def memory_bytes(self) -> int:
        with self._lock:
            return self._bytes

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
            self._bytes = 0
