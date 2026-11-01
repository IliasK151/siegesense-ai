from coachfx import death, mech, rnd

from siegesense_engine.coach.brain import CoachBrain
from siegesense_engine.coach.report import build_report


def test_report_top_problems():
    b = CoachBrain()
    rounds = []
    for n in range(1, 6):
        r = rnd(n, died=True, time_alive_s=10.0, traded=True, repeeks=1 if n in (1, 3, 5) else 0)
        rounds.append(r)
        b.on_death(r, rounds, mech(), death(time_alive_s=10.0))
        b.on_round_end(r, rounds, mech(), 0)
    report = build_report(b, rounds)
    assert [p.rule for p in report.problems][:2] == ["early_death", "repeek"]
    assert report.problems[0].count == 5
    assert report.drill.key == "slow_opening"


def test_report_best_moment():
    rounds = [rnd(1, kills=1), rnd(2, kills=3), rnd(3, kills=3, first_blood=True)]
    report = build_report(CoachBrain(), rounds)
    assert report.best_moment == "Round 3: 3 kills, first blood"


def test_report_drill_mapping():
    b = CoachBrain()
    r = rnd(1, died=True, time_alive_s=60.0, traded=True)
    b.on_death(r, [r], mech(flicks=10, overshoots=5, overshoot_rate=0.5), death())
    assert build_report(b, [r]).drill.key == "overshoot"


def test_report_clean_match():
    report = build_report(CoachBrain(), [rnd(1, result="win")])
    assert report.problems == [] and report.best_moment is None
    assert report.drill.key == "clean"
    assert report.summary_line
