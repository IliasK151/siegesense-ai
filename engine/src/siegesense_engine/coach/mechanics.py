"""Aim and shooting habits measured during Live Mode (the step 2 analysers, reused)."""

from __future__ import annotations

from dataclasses import dataclass

from ..input.events import Button, InputEvent, Key, MouseMove
from ..mechanics.flicks import FlickDetector
from ..mechanics.habits import HabitTracker
from ..mechanics.sensitivity import Conversion


@dataclass(frozen=True)
class MechanicsStats:
    flicks: int
    overshoots: int
    overshoot_rate: float
    shots: int
    moving_shots: int
    moving_shot_rate: float
    crouch_spams_total: int


class LiveMechanics:
    def __init__(self, conversion: Conversion) -> None:
        self._conv = conversion
        self._flicks = FlickDetector()
        self._habits = HabitTracker()
        self._count = 0
        self._overshoots = 0

    def feed(self, events: list[InputEvent]) -> None:
        for e in events:
            if isinstance(e, MouseMove):
                dx, dy = e.dx * self._conv.yaw, e.dy * self._conv.pitch
                self._flicks.move(e.t, dx, dy)
                self._habits.move(e.t, dx, dy)
            elif isinstance(e, Button):
                if e.button == "left" and e.down:
                    self._flicks.shot(e.t)
                self._habits.button(e.t, e.button, e.down)
            elif isinstance(e, Key):
                self._habits.key(e.t, e.vk, e.down)

    def poll(self, now: float) -> None:
        for f in self._flicks.poll(now):
            self._count += 1
            self._overshoots += f.overshoot

    def stats(self) -> MechanicsStats:
        h = self._habits.snapshot()
        return MechanicsStats(
            flicks=self._count,
            overshoots=self._overshoots,
            overshoot_rate=round(self._overshoots / self._count, 4) if self._count else 0.0,
            shots=h.shots,
            moving_shots=h.moving_shots,
            moving_shot_rate=round(h.moving_shots / h.shots, 4) if h.shots else 0.0,
            crouch_spams_total=h.crouch_spams,
        )

    def round_marker(self) -> int:
        return self._habits.snapshot().crouch_spams
