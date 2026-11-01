"""Kill feed reader.

Fast path: find kill lines and the coloured name blocks with plain image processing, then run
recognition-only OCR (~10 ms) on each name. Full text detection (~1 s on a slow CPU) is only a
rare fallback. Work is skipped entirely while the kill feed crop does not change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from .names import clean_name, looks_like_name, same_name
from .ocr import OcrEngine, prep_text

Team = Literal["blue", "orange", "unknown"]
DEDUPE_SECONDS = 10.0
CHANGE_THRESHOLD = 2.0
NAME_GAP_PX = 12
MIN_LINE_PX = 8
FALLBACK_EVERY = 2.0
MIN_NAME_CONFIDENCE = 0.6


@dataclass
class KillEntry:
    killer: str
    victim: str
    killer_team: Team
    victim_team: Team
    confidence: float
    line_y: int
    headshot: bool | None = None  # needs an icon template from a real screenshot


def _hsv(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2HSV)


def _coloured(hsv: np.ndarray) -> np.ndarray:
    return (hsv[..., 1] > 80) & (hsv[..., 2] > 80)


def _runs(active: np.ndarray, max_gap: int) -> list[tuple[int, int]]:
    """Index ranges where ``active`` is true, merging gaps of at most ``max_gap``."""
    runs: list[tuple[int, int]] = []
    idx = np.flatnonzero(active)
    if idx.size == 0:
        return runs
    start = prev = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - prev > max_gap + 1:
            runs.append((start, prev + 1))
            start = i
        prev = i
    runs.append((start, prev + 1))
    return runs


def segment_lines(img: np.ndarray) -> list[tuple[int, int]]:
    # Team-coloured name pixels only: white text and bright scenery would merge every row.
    rows = _coloured(_hsv(img)).sum(axis=1) >= 2
    return [(a, b) for a, b in _runs(rows, 2) if b - a >= MIN_LINE_PX]


def segment_names(line: np.ndarray) -> list[tuple[int, int]]:
    """Leftmost and rightmost coloured blocks of a kill line (killer, victim)."""
    cols = _coloured(_hsv(line)).sum(axis=0) >= 1
    runs = [r for r in _runs(cols, NAME_GAP_PX) if r[1] - r[0] >= 6]
    if len(runs) < 2:
        return []
    return [runs[0], runs[-1]]


def team_of(img: np.ndarray) -> Team:
    hsv = _hsv(img)
    hues = hsv[..., 0][_coloured(hsv)]
    if hues.size < 5:
        return "unknown"
    h = float(np.median(hues))
    if 90 <= h <= 130:
        return "blue"
    if 5 <= h <= 25:
        return "orange"
    return "unknown"


def _plausible(text: str, confidence: float) -> bool:
    return confidence >= MIN_NAME_CONFIDENCE and looks_like_name(text)


class KillFeedReader:
    def __init__(self, ocr: OcrEngine, own_name: str) -> None:
        self._ocr = ocr
        self._own = own_name.lower()
        self._last_crop: np.ndarray | None = None
        self._recent: list[list] = []  # [killer, victim, last_seen_t]
        self._last_fallback = -1e9

    def is_me(self, name: str) -> bool:
        return same_name(name, self._own)

    def reset_change_detection(self) -> None:
        self._last_crop = None

    def _changed(self, img: np.ndarray) -> bool:
        last = self._last_crop
        self._last_crop = img.copy()
        if last is None or last.shape != img.shape:
            return True
        diff = cv2.absdiff(last, img)
        return float(diff.mean()) >= CHANGE_THRESHOLD

    def _name(self, line: np.ndarray, x0: int, x1: int) -> tuple[str, float, Team]:
        pad = 4
        crop = line[:, max(0, x0 - pad) : min(line.shape[1], x1 + pad)]
        text, conf = self._ocr.recognize(prep_text(crop))
        return text.strip(), conf, team_of(crop)

    def _parse_lines(self, img: np.ndarray) -> list[KillEntry]:
        entries: list[KillEntry] = []
        for y0, y1 in segment_lines(img):
            line = img[y0:y1]
            names = segment_names(line)
            if len(names) != 2:
                continue
            killer, kc, kt = self._name(line, *names[0])
            victim, vc, vt = self._name(line, *names[1])
            if not _plausible(killer, kc) or not _plausible(victim, vc):
                continue
            killer, victim = clean_name(killer), clean_name(victim)
            entries.append(KillEntry(killer, victim, kt, vt, min(kc, vc), y0))
        return entries

    def _fallback(self, img: np.ndarray, t: float) -> list[KillEntry]:
        if t - self._last_fallback < FALLBACK_EVERY or _coloured(_hsv(img)).sum() < 50:
            return []
        self._last_fallback = t
        boxes = sorted(self._ocr.detect_and_recognize(img), key=lambda b: (b[2][1], b[2][0]))
        lines: list[list] = []
        for text, conf, (x, y, w, h) in boxes:
            if lines and abs(lines[-1][0][2][1] - y) < h * 0.6:
                lines[-1].append((text, conf, (x, y, w, h)))
            else:
                lines.append([(text, conf, (x, y, w, h))])
        entries = []
        for parts in lines:
            if len(parts) < 2:
                continue
            (kt_, kc, kb), (vt_, vc, vb) = parts[0], parts[-1]
            if not _plausible(kt_, kc) or not _plausible(vt_, vc):
                continue
            k_img = img[kb[1] : kb[1] + kb[3], kb[0] : kb[0] + kb[2]]
            v_img = img[vb[1] : vb[1] + vb[3], vb[0] : vb[0] + vb[2]]
            entries.append(KillEntry(kt_, vt_, team_of(k_img), team_of(v_img), min(kc, vc), kb[1]))
        return entries

    def _is_new(self, e: KillEntry, t: float) -> bool:
        self._recent = [r for r in self._recent if t - r[2] <= DEDUPE_SECONDS]
        for r in self._recent:
            if same_name(r[0], e.killer) and same_name(r[1], e.victim):
                r[2] = t  # still on screen
                return False
        self._recent.append([e.killer, e.victim, t])
        return True

    def read(self, img: np.ndarray, t: float) -> list[KillEntry]:
        """New kill-feed entries since the last call, top line first."""
        if not self._changed(img):
            return []
        entries = self._parse_lines(img)
        if not entries and not segment_lines(img):
            entries = self._fallback(img, t)
        return [e for e in entries if self._is_new(e, t)]
