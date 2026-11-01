"""360° calibration (spec §4.2): the player presses F8, turns exactly one full circle in
game, and presses F8 again. Raw counts of that turn are the ground truth for their aim."""

from __future__ import annotations

import statistics
from typing import Literal

from pydantic import BaseModel

from .input.events import VK, InputEvent, Key, MouseMove

MIN_RUN_COUNTS = 1000
MAX_SPREAD = 0.03
WARN_TOO_SMALL = "That was too small — turn one full circle, then press F8."


class CalibrationState(BaseModel):
    phase: Literal["armed", "measuring", "done", "cancelled"]
    runs: list[int]
    current_counts: int
    target_runs: int = 3
    result: float | None = None
    spread: float | None = None
    warning: str | None = None


class CalibrationSession:
    def __init__(self, hotkey_vk: int = VK.F8, target_runs: int = 3) -> None:
        self._hotkey = hotkey_vk
        self._target = target_runs
        self._phase: Literal["armed", "measuring", "done", "cancelled"] = "armed"
        self._runs: list[int] = []
        self._sum = 0
        self._key_down = False
        self._warning: str | None = None

    def feed(self, events: list[InputEvent]) -> bool:
        if self._phase in ("done", "cancelled"):
            return False
        changed = False
        for e in events:
            if isinstance(e, Key) and e.vk == self._hotkey:
                if not e.down:
                    self._key_down = False
                    continue
                if self._key_down:
                    continue  # auto-repeat
                self._key_down = True
                self._press()
                changed = True
            elif isinstance(e, MouseMove) and self._phase == "measuring":
                self._sum += e.dx
                changed = True
            if self._phase == "done":
                break
        return changed

    def _press(self) -> None:
        if self._phase == "armed":
            self._phase = "measuring"
            self._sum = 0
            return
        counts = abs(self._sum)
        self._sum = 0
        self._phase = "armed"
        if counts < MIN_RUN_COUNTS:
            self._warning = WARN_TOO_SMALL
            return
        self._warning = None
        self._runs.append(counts)
        if len(self._runs) >= self._target:
            self._phase = "done"
            result = statistics.median(self._runs)
            spread = (max(self._runs) - min(self._runs)) / result
            if spread > MAX_SPREAD:
                self._warning = (
                    f"Your runs differ by {round(spread * 100)}% — "
                    "try again slowly for a more exact result."
                )

    def cancel(self) -> None:
        self._phase = "cancelled"

    def state(self) -> CalibrationState:
        result = statistics.median(self._runs) if self._phase == "done" else None
        spread = (max(self._runs) - min(self._runs)) / result if result else None
        return CalibrationState(
            phase=self._phase,
            runs=list(self._runs),
            current_counts=abs(self._sum),
            target_runs=self._target,
            result=result,
            spread=spread,
            warning=self._warning,
        )
