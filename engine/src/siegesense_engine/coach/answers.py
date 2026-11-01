"""Answers to the player's questions, from this match's facts. Uses the local AI when it is
available and grounded; otherwise a keyword-matched answer built from the same facts."""

from __future__ import annotations

from pydantic import BaseModel

from .brain import Tip
from .llm import LocalLLM


class SessionFacts(BaseModel):
    rounds_played: int = 0
    rounds_won: int = 0
    rounds_lost: int = 0
    deaths: int = 0
    first_deaths: int = 0
    untraded_deaths: int = 0
    avg_time_alive_s: float | None = None
    last_death_round: int | None = None
    last_death_killer: str | None = None
    last_death_time_alive_s: float | None = None
    kills: int = 0
    repeeks: int = 0
    flicks: int = 0
    overshoot_pct: int = 0
    moving_shot_pct: int = 0
    recent_tips: list[str] = []


def _keyword(question: str, f: SessionFacts) -> tuple[str, str, dict]:
    q = question.lower()
    if any(w in q for w in ("aim", "flick", "overshoot", "shoot", "spray")):
        return (
            "answer_aim",
            f"This match you overshot {f.overshoot_pct}% of {f.flicks} flicks and fired "
            f"{f.moving_shot_pct}% of shots while moving. Stop on the head, then shoot.",
            {"overshoot_pct": f.overshoot_pct, "flicks": f.flicks, "moving_pct": f.moving_shot_pct},
        )
    if "trade" in q:
        return (
            "answer_trades",
            f"{f.untraded_deaths} of your {f.deaths} deaths weren't traded. Stay closer to a "
            "teammate so they can refrag.",
            {"untraded_deaths": f.untraded_deaths, "deaths": f.deaths},
        )
    if "peek" in q:
        return (
            "answer_repeek",
            f"You re-peeked the same angle {f.repeeks} times after a kill. Move to a new angle "
            "before you peek again.",
            {"repeeks": f.repeeks},
        )
    if any(w in q for w in ("die", "death", "dying", "dead", "first")):
        alive = (
            f" You survive {f.avg_time_alive_s:.0f} seconds on average."
            if f.avg_time_alive_s
            else ""
        )
        return (
            "answer_deaths",
            f"{f.first_deaths} of your {f.deaths} deaths were the first death of the round.{alive} "
            "Let a teammate or your drone take first contact.",
            {
                "first_deaths": f.first_deaths,
                "deaths": f.deaths,
                "avg_time_alive_s": f.avg_time_alive_s,
            },
        )
    if any(w in q for w in ("score", "round", "win", "winning", "losing")):
        return (
            "answer_score",
            f"You're {f.rounds_won}–{f.rounds_lost} in rounds with {f.kills} kills and "
            f"{f.deaths} deaths.",
            {"won": f.rounds_won, "lost": f.rounds_lost, "kills": f.kills, "deaths": f.deaths},
        )
    return (
        "answer_help",
        "I can answer about your aim, deaths, trades, re-peeks and rounds this match.",
        {"rounds_played": f.rounds_played},
    )


class Answerer:
    def __init__(self, llm: LocalLLM | None) -> None:
        self._llm = llm

    async def answer(self, question: str, facts: SessionFacts) -> Tip:
        rule, text, evidence = _keyword(question, facts)
        if self._llm is not None:
            ai = await self._llm.answer(question, facts.model_dump())
            if ai:
                return Tip(rule="ai_answer", slot="answer", round=None, text=ai,
                           evidence={"question": question, **evidence})  # fmt: skip
        return Tip(rule=rule, slot="answer", round=None, text=text,
                   evidence={"question": question, **evidence})  # fmt: skip
