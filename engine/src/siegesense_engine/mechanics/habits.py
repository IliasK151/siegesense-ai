"""Shooting and movement habits (spec §4.5): spray vs tap, shooting while moving,
strafe switches, crouch spam and micro-jitter while aiming down sights."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from ..input.events import VK

TAP_MAX = 0.150  # s
BURST_MAX = 0.600  # s
STRAFE_SWITCH_WINDOW = 0.5  # s
CROUCH_RUN_WINDOW = 2.0  # s
CROUCH_RUN_PRESSES = 3
JITTER_BIN = 0.05  # s
JITTER_MIN, JITTER_MAX = 0.05, 1.0  # degrees per bin
MOVE_KEYS = frozenset({VK.W, VK.A, VK.S, VK.D})


@dataclass
class HabitStats:
    shots: int = 0
    taps: int = 0
    bursts: int = 0
    sprays: int = 0
    moving_shots: int = 0
    strafe_switches: int = 0
    crouch_spams: int = 0
    ads_seconds: float = 0.0
    ads_jitter: int = 0


class HabitTracker:
    def __init__(self) -> None:
        self._stats = HabitStats()
        self._held: set[int] = set()
        self._fire_down_at: float | None = None
        self._last_strafe: tuple[int, float] | None = None
        self._crouches: deque[float] = deque()
        self._in_crouch_run = False
        self._ads_since: float | None = None
        self._last_t = 0.0
        self._jitter_bin: tuple[int, float] | None = None  # (bin index, dx sum)
        self._jitter_prev: tuple[int, float] | None = None

    # -- events --------------------------------------------------------------------------
    def button(self, t: float, button: str, down: bool) -> None:
        self._last_t = max(self._last_t, t)
        if button == "left":
            if down and self._fire_down_at is None:
                self._fire_down_at = t
                self._stats.shots += 1
                if self._held & MOVE_KEYS:
                    self._stats.moving_shots += 1
            elif not down and self._fire_down_at is not None:
                hold = t - self._fire_down_at
                self._fire_down_at = None
                if hold < TAP_MAX:
                    self._stats.taps += 1
                elif hold <= BURST_MAX:
                    self._stats.bursts += 1
                else:
                    self._stats.sprays += 1
        elif button == "right":
            if down and self._ads_since is None:
                self._ads_since = t
            elif not down and self._ads_since is not None:
                self._stats.ads_seconds += t - self._ads_since
                self._ads_since = None
                self._close_jitter_bin()
                self._jitter_prev = None

    def key(self, t: float, vk: int, down: bool) -> None:
        self._last_t = max(self._last_t, t)
        if not down:
            self._held.discard(vk)
            return
        if vk in self._held:
            return  # keyboard auto-repeat
        self._held.add(vk)
        if vk in (VK.A, VK.D):
            if self._last_strafe is not None:
                last_vk, last_t = self._last_strafe
                if last_vk != vk and t - last_t <= STRAFE_SWITCH_WINDOW:
                    self._stats.strafe_switches += 1
            self._last_strafe = (vk, t)
        elif vk == VK.C:
            self._crouches.append(t)
            while self._crouches and t - self._crouches[0] > CROUCH_RUN_WINDOW:
                self._crouches.popleft()
            if len(self._crouches) >= CROUCH_RUN_PRESSES:
                if not self._in_crouch_run:
                    self._stats.crouch_spams += 1
                    self._in_crouch_run = True
            else:
                self._in_crouch_run = False

    def move(self, t: float, dx_deg: float, dy_deg: float) -> None:
        self._last_t = max(self._last_t, t)
        if self._ads_since is None:
            return
        idx = math.floor(t / JITTER_BIN)
        if self._jitter_bin is not None and self._jitter_bin[0] != idx:
            self._close_jitter_bin()
        if self._jitter_bin is None:
            self._jitter_bin = (idx, 0.0)
        self._jitter_bin = (idx, self._jitter_bin[1] + dx_deg)

    # -- output --------------------------------------------------------------------------
    def snapshot(self) -> HabitStats:
        s = HabitStats(**vars(self._stats))
        if self._ads_since is not None:
            s.ads_seconds += max(0.0, self._last_t - self._ads_since)
        return s

    def _close_jitter_bin(self) -> None:
        current = self._jitter_bin
        self._jitter_bin = None
        if current is None:
            return
        prev = self._jitter_prev
        if prev is not None and current[0] == prev[0] + 1:
            a, b = prev[1], current[1]
            small = JITTER_MIN < abs(a) < JITTER_MAX and JITTER_MIN < abs(b) < JITTER_MAX
            if small and (a > 0) != (b > 0):
                self._stats.ads_jitter += 1
        self._jitter_prev = current
