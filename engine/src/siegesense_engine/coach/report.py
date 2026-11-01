"""The end-of-match report (spec §4.8): top 3 problems, best moment, one drill."""

from __future__ import annotations

from pydantic import BaseModel

from ..rounds import RoundSummary
from ..warmup import DRILLS, Drill
from .brain import CoachBrain

MATCH_DRILLS: dict[str, Drill] = {
    "slow_opening": Drill(
        key="slow_opening",
        title="Slow your openings",
        text="Play 3 rounds of Lone Wolf/T-Hunt where you clear every angle with your drone "
        "before entering.",
    ),
    "trade_spacing": Drill(
        key="trade_spacing",
        title="Stay tradeable",
        text="In your next 5 rounds, stay within one room of a teammate when you push.",
    ),
    "reposition": Drill(
        key="reposition",
        title="Reposition after kills",
        text="After every kill in your next match, move to a new angle before you peek again.",
    ),
}
DRILL_FOR = {
    "overshoot_live": DRILLS["overshoot"],
    "moving_shots": DRILLS["counter_strafe"],
    "early_death": MATCH_DRILLS["slow_opening"],
    "first_death": MATCH_DRILLS["slow_opening"],
    "first_death_streak": MATCH_DRILLS["slow_opening"],
    "not_traded": MATCH_DRILLS["trade_spacing"],
    "repeek": MATCH_DRILLS["reposition"],
}


class Problem(BaseModel):
    rule: str
    count: int
    text: str


class MatchReport(BaseModel):
    problems: list[Problem]
    best_moment: str | None
    drill: Drill
    summary_line: str


def build_report(brain: CoachBrain, rounds: list[RoundSummary]) -> MatchReport:
    ranked = sorted(
        ((rule, n) for rule, n in brain.fired.items() if rule != "good_round"),
        key=lambda x: (-x[1], x[0]),
    )[:3]
    problems = [Problem(rule=r, count=n, text=brain.last_texts.get(r, "")) for r, n in ranked]

    best = max(rounds, key=lambda r: (r.kills, r.first_blood, -r.number), default=None)
    best_moment = None
    if best is not None and best.kills > 0:
        best_moment = f"Round {best.number}: {best.kills} kill{'s' if best.kills != 1 else ''}"
        if best.first_blood:
            best_moment += ", first blood"

    drill = DRILL_FOR.get(problems[0].rule, DRILLS["clean"]) if problems else DRILLS["clean"]
    won = sum(r.result == "win" for r in rounds)
    lost = sum(r.result == "loss" for r in rounds)
    deaths = sum(r.died for r in rounds)
    summary = f"{won}–{lost} in rounds, {deaths} death{'s' if deaths != 1 else ''}."
    if problems:
        summary += f" Biggest thing to fix: {drill.title.lower()}."
    return MatchReport(
        problems=problems, best_moment=best_moment, drill=drill, summary_line=summary
    )
