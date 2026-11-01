"""Round timer, team scores and the player's health, read from small fixed HUD crops."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .ocr import OcrEngine, prep_text

_TIMER = re.compile(r"^(\d{1,2})[:.;,]?(\d{2})$")


@dataclass
class Reading[T]:
    value: T | None
    confidence: float


def _clean(text: str) -> str:
    return (
        text.strip()
        .replace(" ", "")
        .replace("O", "0")
        .replace("o", "0")
        .replace("l", "1")
        .replace("I", "1")
    )


def parse_timer(text: str) -> int | None:
    m = _TIMER.match(_clean(text))
    if not m:
        return None
    minutes, seconds = int(m.group(1)), int(m.group(2))
    if seconds >= 60:
        return None
    total = minutes * 60 + seconds
    return total if total <= 600 else None


def _read_int(img: np.ndarray, ocr: OcrEngine, lo: int, hi: int) -> Reading[int]:
    text, conf = ocr.recognize(prep_text(img))
    digits = _clean(text)
    if not digits.isdigit():
        return Reading(None, 0.0 if text else conf)
    value = int(digits)
    return Reading(value, conf) if lo <= value <= hi else Reading(None, 0.0)


def read_timer(img: np.ndarray, ocr: OcrEngine) -> Reading[int]:
    text, conf = ocr.recognize(prep_text(img))
    value = parse_timer(text)
    return Reading(value, conf) if value is not None else Reading(None, 0.0)


def read_score(img: np.ndarray, ocr: OcrEngine) -> Reading[int]:
    return _read_int(img, ocr, 0, 20)


def read_health(img: np.ndarray, ocr: OcrEngine) -> Reading[int]:
    return _read_int(img, ocr, 1, 200)
