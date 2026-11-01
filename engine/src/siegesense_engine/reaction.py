"""Reaction time for Warm-up (beta): a target appears in the centre of the screen while the
mouse is still, then the player starts a flick. Reaction = flick onset - visual change."""

from __future__ import annotations

import statistics
import threading

import numpy as np

CHANGE_THRESHOLD = 12.0  # mean absolute grey difference between consecutive centre frames
STILL_FOR = 0.150  # s without mouse movement before the change
MAX_REACTION = 1.0  # s
MIN_SAMPLES = 3
MOVE_EPS = 0.05  # degrees


class ReactionTimer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prev: np.ndarray | None = None
        self._last_move = -1e9
        self._stimuli: list[float] = []
        self._samples: list[float] = []

    def moved(self, t: float, deg: float) -> None:
        if abs(deg) > MOVE_EPS:
            with self._lock:
                self._last_move = max(self._last_move, t)

    def frame(self, t: float, centre_gray: np.ndarray) -> None:
        img = centre_gray.astype(np.int16)
        with self._lock:
            prev, self._prev = self._prev, img
            if prev is None or prev.shape != img.shape:
                return
            change = float(np.abs(img - prev).mean())
            if change > CHANGE_THRESHOLD and t - self._last_move >= STILL_FOR:
                self._stimuli.append(t)
                self._stimuli = [s for s in self._stimuli if t - s <= 5.0]

    def flick_onset(self, t: float) -> None:
        with self._lock:
            candidates = [s for s in self._stimuli if 0 < t - s <= MAX_REACTION]
            if not candidates:
                return
            stim = max(candidates)
            self._samples.append((t - stim) * 1000)
            self._stimuli = [s for s in self._stimuli if s > t]  # one sample per stimulus

    def samples(self) -> list[float]:
        with self._lock:
            return list(self._samples)

    def median_ms(self) -> float | None:
        s = self.samples()
        return round(statistics.median(s), 1) if len(s) >= MIN_SAMPLES else None
