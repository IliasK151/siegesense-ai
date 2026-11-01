"""Warm-up Mode (spec §5): live aim metrics, a warm-up score and a drill suggestion."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .input.events import Button, InputEvent, Key, MouseMove
from .mechanics.flicks import Flick, FlickConfig, FlickDetector
from .mechanics.habits import HabitTracker
from .mechanics.sensitivity import Conversion
from .reaction import ReactionTimer

MIN_FLICKS_FOR_SCORE = 5
MIN_FLICKS_FOR_DRILL = 10
MSG_TOO_FEW = "Not enough flicks yet (need 10) — no score or drill for this session."
MSG_NO_DRILL = "Score is ready; play a bit longer for a drill suggestion."


class WarmupMetrics(BaseModel):
    elapsed_s: float
    flicks: int
    corrected: int
    overshoots: int
    overshoot_rate: float
    correction_rate: float
    avg_amplitude: float
    avg_peak_speed: float
    shots: int
    taps: int
    bursts: int
    sprays: int
    moving_shots: int
    moving_shot_rate: float
    strafe_switches: int
    crouch_spams: int
    ads_jitter_per_s: float
    reaction_ms: float | None = None
    reactions: int = 0
    score: int | None
    conversion: Literal["calibrated", "estimated"]

    @classmethod
    def empty(cls, conversion: Literal["calibrated", "estimated"]) -> WarmupMetrics:
        zero = {name: 0 for name in cls.model_fields}
        return cls(**{**zero, "score": None, "reaction_ms": None, "conversion": conversion})


class FlickOut(BaseModel):
    id: int
    t_peak: float
    amplitude: float
    peak_speed: float
    duration_ms: float
    direction: float
    reversal: float
    corrected: bool
    overshoot: bool
    shot: bool
    trace: list[list[float]]


class Drill(BaseModel):
    key: str
    title: str
    text: str


class HistoryPoint(BaseModel):
    started_at: str
    score: int | None


class WarmupSummary(BaseModel):
    id: int | None
    started_at: str
    duration_s: float
    metrics: WarmupMetrics
    drill: Drill | None
    message: str
    history: list[HistoryPoint]


DRILLS: dict[str, Drill] = {
    d.key: d
    for d in [
        Drill(
            key="overshoot",
            title="Overshooting your flicks",
            text="In the Shooting Range, flick between two targets at about 70% speed for 20 "
            "reps. Focus on stopping on the head, not past it.",
        ),
        Drill(
            key="corrections",
            title="Too many micro-corrections",
            text="Pick a target 60° away and flick to it 20 times without adjusting after. "
            "Accuracy first, speed comes later.",
        ),
        Drill(
            key="counter_strafe",
            title="Shooting while moving",
            text="Strafe, stop, then shoot. Do 20 strafe-stop-tap reps on a bot and let your "
            "movement settle before each shot.",
        ),
        Drill(
            key="smooth_ads",
            title="Shaky while aiming down sights",
            text="Hold ADS on a static target for 5 seconds, 10 times, keeping your crosshair "
            "still. Relax your grip.",
        ),
        Drill(
            key="clean",
            title="Clean flicks",
            text="Your flicks are clean. Raise the difficulty: farther targets, faster switches.",
        ),
    ]
}


def compute_score(flicks: int, overshoot_rate: float, correction_rate: float) -> int | None:
    if flicks < MIN_FLICKS_FOR_SCORE:
        return None
    return round(100 * (0.6 * (1 - overshoot_rate) + 0.4 * (1 - correction_rate)))


def choose_drill(m: WarmupMetrics) -> Drill | None:
    if m.flicks < MIN_FLICKS_FOR_DRILL:
        return None
    if m.overshoot_rate > 0.30:
        return DRILLS["overshoot"]
    if m.correction_rate > 0.40:
        return DRILLS["corrections"]
    if m.moving_shot_rate > 0.50:
        return DRILLS["counter_strafe"]
    if m.ads_jitter_per_s > 4:
        return DRILLS["smooth_ads"]
    return DRILLS["clean"]


def summarize(
    m: WarmupMetrics, started_at: datetime, duration_s: float, history: list[HistoryPoint]
) -> WarmupSummary:
    drill = choose_drill(m)
    if m.flicks < MIN_FLICKS_FOR_SCORE:
        message = MSG_TOO_FEW
    elif drill is None:
        message = MSG_NO_DRILL
    else:
        message = drill.title
    return WarmupSummary(
        id=None,
        started_at=started_at.isoformat(),
        duration_s=round(duration_s, 1),
        metrics=m,
        drill=drill,
        message=message,
        history=history,
    )


def _flick_out(fid: int, f: Flick) -> FlickOut:
    return FlickOut(
        id=fid,
        t_peak=f.t_peak,
        amplitude=round(f.amplitude, 2),
        peak_speed=round(f.peak_speed, 1),
        duration_ms=round(f.duration_ms, 1),
        direction=round(f.direction, 1),
        reversal=round(f.reversal, 2),
        corrected=f.corrected,
        overshoot=f.overshoot,
        shot=f.shot,
        trace=[[t, p] for t, p in f.trace],
    )


class WarmupSession:
    def __init__(
        self,
        conversion: Conversion,
        started_at: datetime,
        t0: float,
        flick_config: FlickConfig | None = None,
    ) -> None:
        self.conversion = conversion
        self.started_at = started_at
        self.t0 = t0
        self._flicks = FlickDetector(flick_config)
        self._habits = HabitTracker()
        self._reaction = ReactionTimer()
        self._done: list[FlickOut] = []

    def feed(self, events: list[InputEvent]) -> None:
        for e in events:
            if isinstance(e, MouseMove):
                dx, dy = e.dx * self.conversion.yaw, e.dy * self.conversion.pitch
                self._flicks.move(e.t, dx, dy)
                self._habits.move(e.t, dx, dy)
                self._reaction.moved(e.t, abs(dx) + abs(dy))
            elif isinstance(e, Button):
                if e.button == "left" and e.down:
                    self._flicks.shot(e.t)
                self._habits.button(e.t, e.button, e.down)
            elif isinstance(e, Key):
                self._habits.key(e.t, e.vk, e.down)

    def frame(self, t: float, centre_gray) -> None:
        """A downscaled grey crop of the screen centre (from screen capture, if available)."""
        self._reaction.frame(t, centre_gray)

    def poll(self, now: float) -> list[FlickOut]:
        flicks = self._flicks.poll(now)
        for f in flicks:
            self._reaction.flick_onset(f.t_onset)
        new = [_flick_out(len(self._done) + i + 1, f) for i, f in enumerate(flicks)]
        self._done.extend(new)
        return new

    def metrics(self, now: float) -> WarmupMetrics:
        h = self._habits.snapshot()
        n = len(self._done)
        corrected = sum(f.corrected for f in self._done)
        overshoots = sum(f.overshoot for f in self._done)
        over_rate = overshoots / n if n else 0.0
        corr_rate = corrected / n if n else 0.0
        return WarmupMetrics(
            elapsed_s=round(max(0.0, now - self.t0), 2),
            flicks=n,
            corrected=corrected,
            overshoots=overshoots,
            overshoot_rate=round(over_rate, 4),
            correction_rate=round(corr_rate, 4),
            avg_amplitude=round(sum(f.amplitude for f in self._done) / n, 2) if n else 0.0,
            avg_peak_speed=round(sum(f.peak_speed for f in self._done) / n, 1) if n else 0.0,
            shots=h.shots,
            taps=h.taps,
            bursts=h.bursts,
            sprays=h.sprays,
            moving_shots=h.moving_shots,
            moving_shot_rate=round(h.moving_shots / h.shots, 4) if h.shots else 0.0,
            strafe_switches=h.strafe_switches,
            crouch_spams=h.crouch_spams,
            ads_jitter_per_s=round(h.ads_jitter / h.ads_seconds, 2) if h.ads_seconds else 0.0,
            reaction_ms=self._reaction.median_ms(),
            reactions=len(self._reaction.samples()),
            score=compute_score(n, over_rate, corr_rate),
            conversion=self.conversion.source,
        )
