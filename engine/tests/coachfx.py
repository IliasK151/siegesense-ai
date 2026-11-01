"""Helpers for coach tests."""

from siegesense_engine.coach.mechanics import MechanicsStats
from siegesense_engine.rounds import RoundSummary


def rnd(n, **kw) -> RoundSummary:
    base = dict(number=n, started_t=n * 100.0, ended_t=n * 100.0 + 90, result="loss")
    return RoundSummary(**{**base, **kw})


def mech(**kw) -> MechanicsStats:
    base = dict(flicks=0, overshoots=0, overshoot_rate=0.0, shots=0, moving_shots=0,
                moving_shot_rate=0.0, crouch_spams_total=0)  # fmt: skip
    return MechanicsStats(**{**base, **kw})


def death(**kw) -> dict:
    return {"killer": "Bandit.X", "time_alive_s": 60.0, "first_death": False, **kw}
