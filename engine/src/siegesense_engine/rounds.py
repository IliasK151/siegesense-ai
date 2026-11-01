"""Builds the match timeline from HUD readings and the player's own aim (spec §4.6):
rounds, phases, kills, deaths, trades, first blood and re-peeks."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel
from rapidfuzz import fuzz

from .hud.reader import HudReading, KillEntryModel

PREP_MAX = 45  # s; a round that starts at or under this is in the preparation phase
JUMP_UP = 10  # s; timer jumping up by more than this means a new phase/round
END_AFTER_NO_TIMER = 4.0  # s without a readable timer once action started
TRADE_WINDOW = 5.0  # s
DEATH_MATCH_WINDOW = 3.0  # s between the kill feed and the health disappearing
HEALTH_GONE_FOR = 1.0  # s
LOW_CONFIDENCE_AFTER = 4.0  # s without health confirmation → record as low confidence
REPEEK_WINDOW = 3.0  # s after your kill
REPEEK_AWAY = 10.0  # degrees
REPEEK_BACK = 3.0  # degrees
NAME_MATCH = 85


class LiveEvent(BaseModel):
    kind: Literal["round_start", "phase", "kill", "death", "round_end", "repeek"]
    t: float
    round: int
    data: dict[str, Any] = {}
    confidence: Literal["ok", "low"] = "ok"


class RoundSummary(BaseModel):
    number: int
    phase_seen: list[Literal["prep", "action"]] = []
    started_t: float
    ended_t: float | None = None
    result: Literal["win", "loss"] | None = None
    kills: int = 0
    died: bool = False
    death_confidence: Literal["ok", "low"] | None = None
    time_alive_s: float | None = None
    first_blood: bool = False
    first_death: bool = False
    traded: bool = False
    traded_teammate: int = 0
    repeeks: int = 0


@dataclass
class _Kill:
    t: float
    entry: KillEntryModel


@dataclass
class _PendingDeath:
    t: float
    killer: str


@dataclass
class _PendingRepeek:
    t: float
    yaw: float
    away: bool = False


@dataclass
class _Round:
    summary: RoundSummary
    phase: Literal["prep", "action"] | None = None
    action_started: bool = False
    feed: list[_Kill] = field(default_factory=list)
    death_t: float | None = None
    killer: str | None = None


def _same(a: str, b: str) -> bool:
    return fuzz.ratio(a.lower(), b.lower()) >= NAME_MATCH


class RoundTracker:
    def __init__(self, own_name: str) -> None:
        self._own = own_name
        self._rounds: list[_Round] = []
        self._current: _Round | None = None
        self._last_timer: int | None = None
        self._timer_gone_since: float | None = None
        self._scores: tuple[int, int] | None = None
        self._my_team: str | None = None
        self._pending_death: _PendingDeath | None = None
        self._health_gone_since: float | None = None
        self._yaw_t: list[float] = []
        self._yaw: list[float] = []
        self._repeeks: list[_PendingRepeek] = []
        self._queued: list[LiveEvent] = []

    # -- public ------------------------------------------------------------------------
    def rounds(self) -> list[RoundSummary]:
        return [r.summary for r in self._rounds]

    def input(self, t: float, yaw_deg: float) -> None:
        """Cumulative horizontal aim angle (degrees) from the player's mouse."""
        if self._yaw_t and t < self._yaw_t[-1]:
            return
        self._yaw_t.append(t)
        self._yaw.append(yaw_deg)
        if len(self._yaw_t) > 20000:
            del self._yaw_t[:10000], self._yaw[:10000]
        self._check_repeeks(t, yaw_deg)

    def hud(self, r: HudReading) -> list[LiveEvent]:
        events, self._queued = self._queued, []
        events += self._track_timer(r)
        events += self._track_score(r)
        for k in r.kills:
            events += self._on_kill(r.t, k)
        events += self._track_death(r)
        return events

    # -- rounds and phases -------------------------------------------------------------
    def _event(self, kind, t, data=None, confidence="ok") -> LiveEvent:
        number = self._current.summary.number if self._current else len(self._rounds)
        return LiveEvent(kind=kind, t=t, round=number, data=data or {}, confidence=confidence)

    def _start_round(self, t: float, timer: int) -> list[LiveEvent]:
        events = self._end_round(t, None) if self._current else []
        number = len(self._rounds) + 1
        rnd = _Round(RoundSummary(number=number, started_t=t))
        self._rounds.append(rnd)
        self._current = rnd
        self._pending_death = None
        self._health_gone_since = None
        events.append(self._event("round_start", t))
        events += self._set_phase(t, "prep" if timer <= PREP_MAX else "action")
        return events

    def _set_phase(self, t: float, phase: Literal["prep", "action"]) -> list[LiveEvent]:
        rnd = self._current
        assert rnd is not None
        rnd.phase = phase
        rnd.summary.phase_seen.append(phase)
        if phase == "action":
            rnd.action_started = True
        return [self._event("phase", t, {"phase": phase})]

    def _end_round(self, t: float, result: Literal["win", "loss"] | None) -> list[LiveEvent]:
        rnd = self._current
        if rnd is None:
            return []
        events = self._flush_death(t, force=True)
        s = rnd.summary
        s.ended_t = t
        s.result = result
        if s.time_alive_s is None:
            s.time_alive_s = round(t - s.started_t, 1)
        self._current = None
        events.append(self._event("round_end", t, {"result": result}))
        return events

    def _track_timer(self, r: HudReading) -> list[LiveEvent]:
        events: list[LiveEvent] = []
        if r.timer is None:
            if self._current and self._current.action_started:
                self._timer_gone_since = self._timer_gone_since or r.t
                if r.t - self._timer_gone_since >= END_AFTER_NO_TIMER:
                    events += self._end_round(r.t, None)
            return events
        self._timer_gone_since = None
        last = self._last_timer
        self._last_timer = r.timer
        if self._current is None:
            return self._start_round(r.t, r.timer)
        if last is not None and r.timer > last + JUMP_UP:
            if self._current.phase == "prep":
                return self._set_phase(r.t, "action")
            return self._start_round(r.t, r.timer)
        return events

    def _track_score(self, r: HudReading) -> list[LiveEvent]:
        if r.score_mine is None or r.score_theirs is None:
            return []
        now = (r.score_mine, r.score_theirs)
        before, self._scores = self._scores, now
        if before is None or now == before:
            return []
        if now[0] > before[0] and now[1] == before[1]:
            result: Literal["win", "loss"] | None = "win"
        elif now[1] > before[1] and now[0] == before[0]:
            result = "loss"
        else:
            return []  # a misread or a new match; ignore
        if self._current is not None:
            return self._end_round(r.t, result)
        # The round already ended on a timeout; attach the result.
        if self._rounds and self._rounds[-1].summary.result is None:
            self._rounds[-1].summary.result = result
        return []

    # -- kills and deaths --------------------------------------------------------------
    def _is_teammate(self, team: str, name: str) -> bool:
        return self._my_team is not None and team == self._my_team and not _same(name, self._own)

    def _on_kill(self, t: float, k: KillEntryModel) -> list[LiveEvent]:
        rnd = self._current
        if rnd is None:
            return []
        if k.killer_is_me and k.killer_team != "unknown":
            self._my_team = k.killer_team
        if k.victim_is_me and k.victim_team != "unknown":
            self._my_team = k.victim_team
        first = not rnd.feed
        rnd.feed.append(_Kill(t, k))
        s = rnd.summary
        events: list[LiveEvent] = []

        if k.killer_is_me:
            s.kills += 1
            s.first_blood = s.first_blood or first
            avenged = any(
                _same(p.entry.killer, k.victim)
                and self._is_teammate(p.entry.victim_team, p.entry.victim)
                and 0 <= t - p.t <= TRADE_WINDOW
                for p in rnd.feed[:-1]
            )
            if avenged:
                s.traded_teammate += 1
            events.append(
                self._event("kill", t, {"victim": k.victim, "first_blood": first, "trade": avenged})
            )
            self._repeeks.append(_PendingRepeek(t, self._yaw_at(t)))
        elif k.victim_is_me and rnd.death_t is None:
            s.first_death = first
            rnd.death_t = t
            rnd.killer = k.killer
            self._pending_death = _PendingDeath(t, k.killer)
        elif rnd.death_t is not None and rnd.killer and _same(k.victim, rnd.killer):
            if self._is_teammate(k.killer_team, k.killer) and t - rnd.death_t <= TRADE_WINDOW:
                s.traded = True
        return events

    def _track_death(self, r: HudReading) -> list[LiveEvent]:
        timer_running = r.timer is not None
        if r.health is None and timer_running:
            self._health_gone_since = self._health_gone_since or r.t
        elif r.health is not None:
            self._health_gone_since = None
        return self._flush_death(r.t)

    def _flush_death(self, now: float, force: bool = False) -> list[LiveEvent]:
        pending, rnd = self._pending_death, self._current
        if pending is None or rnd is None:
            return []
        gone = self._health_gone_since
        confirmed = (
            gone is not None
            and abs(gone - pending.t) <= DEATH_MATCH_WINDOW
            and now - gone >= HEALTH_GONE_FOR
        )
        if not confirmed and not force and now - pending.t < LOW_CONFIDENCE_AFTER:
            return []
        self._pending_death = None
        confidence: Literal["ok", "low"] = "ok" if confirmed else "low"
        s = rnd.summary
        s.died = True
        s.death_confidence = confidence
        s.time_alive_s = round(pending.t - s.started_t, 1)
        return [
            self._event(
                "death",
                pending.t,
                {
                    "killer": pending.killer,
                    "time_alive_s": s.time_alive_s,
                    "first_death": s.first_death,
                },
                confidence,
            )
        ]

    # -- re-peeks ----------------------------------------------------------------------
    def _yaw_at(self, t: float) -> float:
        i = bisect.bisect_right(self._yaw_t, t) - 1
        return self._yaw[i] if i >= 0 else 0.0

    def _check_repeeks(self, t: float, yaw: float) -> None:
        keep = []
        for p in self._repeeks:
            if t - p.t > REPEEK_WINDOW:
                continue
            delta = abs(yaw - p.yaw)
            if delta >= REPEEK_AWAY:
                p.away = True
                keep.append(p)
            elif p.away and delta <= REPEEK_BACK:
                if self._current is not None:
                    self._current.summary.repeeks += 1
                self._queued.append(
                    self._event("repeek", t, {"seconds_after_kill": round(t - p.t, 2)})
                )
            else:
                keep.append(p)
        self._repeeks = keep
