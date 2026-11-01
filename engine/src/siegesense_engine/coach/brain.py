"""The rule-based coach (spec §4.8). Always available, instant, and every tip says why.

Thresholds are first versions written from Siege fundamentals; they live here so they can be
tuned after real matches.
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..rounds import RoundSummary
from .mechanics import MechanicsStats

RECENT = 5
Slot = Literal["death", "round_end", "answer"]


class Tip(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    rule: str
    slot: Slot
    round: int | None
    text: str
    evidence: dict[str, Any] = {}
    spoken: bool = True


@dataclass
class Ctx:
    rnd: RoundSummary
    recent: list[RoundSummary]
    mech: MechanicsStats
    death: dict[str, Any]
    crouch: int


Check = Callable[[Ctx], tuple[str, dict[str, Any]] | None]


@dataclass(frozen=True)
class Rule:
    id: str
    slots: tuple[str, ...]
    priority: int
    cooldown: int
    check: Check


def _early_death(c: Ctx):
    t = c.death.get("time_alive_s")
    if t is None or t >= 25:
        return None
    text = (
        f"You died {t:.0f} seconds into the round. Slow your opening — clear one angle at a "
        "time and let utility go first."
    )
    return text, {"time_alive_s": t}


def _first_death(c: Ctx):
    if not c.rnd.first_death:
        return None
    text = (
        "You took the first death. Don't take the opening fight alone — wait for a drone or a "
        "teammate before you swing."
    )
    return text, {"first_death": True, "round": c.rnd.number}


def _not_traded(c: Ctx):
    deaths = [r for r in c.recent if r.died]
    untraded = [r for r in deaths if not r.traded]
    if c.rnd.traded or len(untraded) < 2:
        return None
    n, m = len(untraded), len(deaths)
    text = (
        f"Your deaths aren't getting traded ({n} of the last {m}). Play closer to a teammate so "
        "they can refrag."
    )
    return text, {"untraded_deaths": n, "recent_deaths": m}


def _overshoot(c: Ctx):
    if c.mech.flicks < 10 or c.mech.overshoot_rate <= 0.30:
        return None
    pct = round(c.mech.overshoot_rate * 100)
    text = (
        f"You're overshooting {pct}% of your flicks this match. Slow the end of your flick and "
        "stop on the head."
    )
    return text, {"flicks": c.mech.flicks, "overshoots": c.mech.overshoots, "overshoot_pct": pct}


def _moving_shots(c: Ctx):
    if c.mech.shots < 15 or c.mech.moving_shot_rate <= 0.50:
        return None
    pct = round(c.mech.moving_shot_rate * 100)
    text = (
        f"{pct}% of your shots were fired while moving. Stop, then shoot — your first bullets "
        "will land."
    )
    return text, {"shots": c.mech.shots, "moving_shots": c.mech.moving_shots, "moving_pct": pct}


def _repeek(c: Ctx):
    if c.rnd.repeeks < 1:
        return None
    text = (
        "You re-peeked the same angle after a kill. After a kill, reposition — they know where "
        "you are."
    )
    return text, {"repeeks": c.rnd.repeeks, "round": c.rnd.number}


def _first_death_streak(c: Ctx):
    n = sum(r.first_death for r in c.recent)
    if n < 3:
        return None
    m = len(c.recent)
    text = (
        f"You've died first in {n} of the last {m} rounds. Next round, let a teammate take "
        "first contact."
    )
    return text, {"first_deaths": n, "rounds": m}


def _crouch_spam(c: Ctx):
    if c.crouch < 2:
        return None
    text = "Crouch-spamming is throwing your aim off. Crouch once to change height, then hold."
    return text, {"crouch_spam_runs": c.crouch}


def _good_round(c: Ctx):
    r = c.rnd
    if r.result != "win" or not (r.first_blood or r.kills >= 2):
        return None
    what = ", ".join(
        x
        for x in [
            f"{r.kills} kills" if r.kills >= 2 else "",
            "first blood" if r.first_blood else "",
        ]
        if x
    )
    return f"Good round — {what}. Keep that tempo.", {
        "kills": r.kills,
        "first_blood": r.first_blood,
    }


RULES: list[Rule] = [
    Rule("early_death", ("death",), 70, 1, _early_death),
    Rule("first_death", ("death",), 80, 2, _first_death),
    Rule("not_traded", ("death",), 60, 2, _not_traded),
    Rule("overshoot_live", ("death", "round_end"), 65, 3, _overshoot),
    Rule("moving_shots", ("round_end",), 50, 3, _moving_shots),
    Rule("repeek", ("round_end",), 75, 2, _repeek),
    Rule("first_death_streak", ("round_end",), 85, 3, _first_death_streak),
    Rule("crouch_spam", ("round_end",), 40, 4, _crouch_spam),
    Rule("good_round", ("round_end",), 30, 2, _good_round),
]
PRIORITY = {r.id: r.priority for r in RULES}


class CoachBrain:
    def __init__(self) -> None:
        self.fired: Counter[str] = Counter()
        self.last_texts: dict[str, str] = {}
        self._last_round: dict[str, int] = {}
        self._streak: dict[str, int] = {}
        self._delivered: dict[int, set[str]] = {}

    def _pick(self, slot: Slot, ctx: Ctx) -> Tip | None:
        number = ctx.rnd.number
        done = self._delivered.setdefault(number, set())
        best: tuple[Rule, str, dict] | None = None
        for rule in RULES:
            if slot not in rule.slots or rule.id in done:
                continue
            last = self._last_round.get(rule.id)
            if last is not None and number - last < rule.cooldown:
                continue
            hit = rule.check(ctx)
            if hit is not None and (best is None or rule.priority > best[0].priority):
                best = (rule, *hit)
        if best is None:
            return None
        rule, text, evidence = best
        last = self._last_round.get(rule.id)
        streak = self._streak.get(rule.id, 0) + 1 if last == number - 1 else 1
        self._streak[rule.id] = streak
        if streak >= 2:
            text = f"{text} (that's {streak} rounds in a row)"
        self._last_round[rule.id] = number
        self.fired[rule.id] += 1
        self.last_texts[rule.id] = text
        done.add(rule.id)
        return Tip(rule=rule.id, slot=slot, round=number, text=text, evidence=evidence)

    def on_death(
        self,
        rnd: RoundSummary,
        history: list[RoundSummary],
        mech: MechanicsStats,
        death: dict[str, Any],
    ) -> Tip | None:
        return self._pick("death", Ctx(rnd, history[-RECENT:], mech, death, 0))

    def on_round_end(
        self,
        rnd: RoundSummary,
        history: list[RoundSummary],
        mech: MechanicsStats,
        round_crouch_spams: int,
    ) -> Tip | None:
        return self._pick("round_end", Ctx(rnd, history[-RECENT:], mech, {}, round_crouch_spams))
