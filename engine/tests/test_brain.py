from coachfx import death, mech, rnd

from siegesense_engine.coach.brain import CoachBrain

NO = mech()


def died(n, **kw):
    return rnd(n, died=True, time_alive_s=kw.pop("t", 60.0), **kw)


def test_early_death():
    b = CoachBrain()
    r = died(1, t=12.0)
    tip = b.on_death(r, [r], NO, death(time_alive_s=12.0))
    assert tip.rule == "early_death" and "12 seconds" in tip.text
    assert tip.evidence["time_alive_s"] == 12.0 and tip.round == 1 and tip.slot == "death"


def test_no_death_tip_for_a_normal_death():
    b = CoachBrain()
    r = died(1, t=70.0, traded=True)
    assert b.on_death(r, [r], NO, death(time_alive_s=70.0)) is None


def test_first_death_beats_early_death():
    b = CoachBrain()
    r = died(1, t=10.0, first_death=True)
    assert b.on_death(r, [r], NO, death(time_alive_s=10.0, first_death=True)).rule == "first_death"


def test_not_traded_needs_two_recent():
    b = CoachBrain()
    h = [died(1), died(2)]
    tip = b.on_death(h[-1], h, NO, death())
    assert tip.rule == "not_traded" and "2 of the last 2" in tip.text
    b2 = CoachBrain()
    h2 = [died(1, traded=True), died(2)]
    assert b2.on_death(h2[-1], h2, NO, death()) is None


def test_overshoot_live_threshold():
    b = CoachBrain()
    r = died(1, traded=True)
    hi = mech(flicks=10, overshoots=4, overshoot_rate=0.4)
    assert b.on_death(r, [r], hi, death()).rule == "overshoot_live"
    b2 = CoachBrain()
    lo = mech(flicks=10, overshoots=3, overshoot_rate=0.3)
    assert b2.on_death(r, [r], lo, death()) is None
    b3 = CoachBrain()
    few = mech(flicks=9, overshoots=9, overshoot_rate=1.0)
    assert b3.on_death(r, [r], few, death()) is None


def test_moving_shots_round_end():
    b = CoachBrain()
    r = rnd(1)
    tip = b.on_round_end(r, [r], mech(shots=20, moving_shots=12, moving_shot_rate=0.6), 0)
    assert tip.rule == "moving_shots" and "60%" in tip.text


def test_repeek_round_end():
    b = CoachBrain()
    r = rnd(1, repeeks=1)
    assert b.on_round_end(r, [r], NO, 0).rule == "repeek"


def test_first_death_streak():
    b = CoachBrain()
    h = [rnd(i, died=True, first_death=i != 2) for i in range(1, 5)]
    tip = b.on_round_end(h[-1], h, NO, 0)
    assert tip.rule == "first_death_streak" and "3 of the last 4" in tip.text


def test_crouch_spam():
    b = CoachBrain()
    r = rnd(1)
    assert b.on_round_end(r, [r], NO, 2).rule == "crouch_spam"
    assert CoachBrain().on_round_end(r, [r], NO, 1) is None


def test_good_round():
    b = CoachBrain()
    r = rnd(1, result="win", first_blood=True, kills=1)
    tip = b.on_round_end(r, [r], NO, 0)
    assert tip.rule == "good_round" and "first blood" in tip.text
    assert CoachBrain().on_round_end(rnd(1, result="win", kills=1), [rnd(1)], NO, 0) is None


def test_priority_order():
    b = CoachBrain()
    r = rnd(1, repeeks=1, result="win", kills=2)
    assert b.on_round_end(r, [r], NO, 3).rule == "repeek"


def test_cooldown():
    b = CoachBrain()
    r1 = rnd(1, repeeks=1)
    assert b.on_round_end(r1, [r1], NO, 0).rule == "repeek"
    r2 = rnd(2, repeeks=1)
    assert b.on_round_end(r2, [r1, r2], NO, 0) is None  # cooldown 2
    r3 = rnd(3, repeeks=1)
    assert b.on_round_end(r3, [r1, r2, r3], NO, 0).rule == "repeek"


def test_repeat_suffix():
    b = CoachBrain()
    for n in (1, 2, 3):
        r = died(n, t=10.0, traded=True)
        tip = b.on_death(r, [r], NO, death(time_alive_s=10.0))
    assert tip.rule == "early_death"
    assert tip.text.endswith("(that's 3 rounds in a row)")


def test_one_tip_per_break():
    b = CoachBrain()
    r = died(1, t=40.0, traded=True)
    hi = mech(flicks=12, overshoots=6, overshoot_rate=0.5)
    first = b.on_death(r, [r], hi, death(time_alive_s=40.0))
    assert first.rule == "overshoot_live"
    second = b.on_round_end(r, [r], hi, 0)
    assert second is None or second.rule != "overshoot_live"
    assert b.fired["overshoot_live"] == 1
