"""Text recognition for HUD crops (RapidOCR, ONNX on CPU; models ship inside the package)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Protocol

import cv2
import numpy as np

log = logging.getLogger(__name__)

DetResult = list[tuple[str, float, tuple[int, int, int, int]]]


class OcrEngine(Protocol):
    def recognize(self, img: np.ndarray) -> tuple[str, float]: ...

    def detect_and_recognize(self, img: np.ndarray) -> DetResult: ...


def prep_text(img: np.ndarray) -> np.ndarray:
    """Grey, upscale small crops, Otsu threshold to white text on black, pad. Returns BGR."""
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gray.shape[0] < 32:
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if (bw > 0).mean() > 0.5:  # mostly white → text was dark; invert
        bw = 255 - bw
    bw = cv2.copyMakeBorder(bw, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=0)
    return cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)


class RapidOcrEngine:
    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    def _get(self):
        if self._engine is None:
            from rapidocr import RapidOCR

            logging.getLogger("RapidOCR").setLevel(logging.ERROR)
            # Two threads at most: OCR must not compete with the game for CPU.
            self._engine = RapidOCR(
                params={
                    "Global.log_level": "error",
                    "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                    "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                }
            )
        return self._engine

    def warm_up(self) -> None:
        self.recognize(np.zeros((32, 64, 3), np.uint8))

    def recognize(self, img: np.ndarray) -> tuple[str, float]:
        with self._lock:
            out = self._get()(img, use_det=False, use_cls=False, use_rec=True)
        texts = getattr(out, "txts", None) or ()
        scores = getattr(out, "scores", None) or ()
        if not texts:
            return "", 0.0
        return str(texts[0]), float(scores[0]) if scores else 0.0

    def detect_and_recognize(self, img: np.ndarray) -> DetResult:
        with self._lock:
            out = self._get()(img, use_det=True, use_cls=False, use_rec=True)
        boxes = getattr(out, "boxes", None)
        if boxes is None or not out.txts:
            return []
        result: DetResult = []
        for text, score, box in zip(out.txts, out.scores, boxes, strict=False):
            xs, ys = [int(p[0]) for p in box], [int(p[1]) for p in box]
            result.append(
                (str(text), float(score), (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
            )
        return result


class FakeOcr:
    """Test double: ``mapping(img) -> (text, confidence)``; counts calls."""

    def __init__(
        self,
        mapping: Callable[[np.ndarray], tuple[str, float]],
        detect: Callable[[np.ndarray], DetResult] | None = None,
    ) -> None:
        self._mapping = mapping
        self._detect = detect or (lambda img: [])
        self.calls = 0
        self.detect_calls = 0

    def recognize(self, img: np.ndarray) -> tuple[str, float]:
        self.calls += 1
        return self._mapping(img)

    def detect_and_recognize(self, img: np.ndarray) -> DetResult:
        self.detect_calls += 1
        return self._detect(img)
