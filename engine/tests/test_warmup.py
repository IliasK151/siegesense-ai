from datetime import UTC, datetime

import pytest
from synth import end_time, flick, to_counts

from siegesense_engine.input.events import Button
from siegesense_engine.mechanics.sensitivity import Conversion
from siegesense_engine.warmup import WarmupSession, choose_drill, summarize

CONV = Conversion(yaw=0.01, pitch=0.01, source="calibrated")
START = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def session_with(n_flicks: int, n_overshoot: int):
    s = WarmupSession(CONV, START, t0=0.0)
    out = []
    t = 1.0
    for i in range(n_flicks):
        over = 6 if i < n_overshoot else 0
        samples = flick(t, 30, 0.12, angle_deg=0 if i % 2 == 0 else 180, overshoot=over)
        events = to_counts(samples, CONV.yaw)
        shot_t = end_time(samples) + 0.1
        events += [Button(shot_t, "left", True), Button(shot_t + 0.05, "left", False)]
        s.feed(events)
        out += s.poll(t + 0.5)
        t += 1.2
    out += s.poll(t + 2)
    return s, out, t + 2


def test_metrics_from_synthetic_session():
    s, flicks, now = session_with(10, 4)
    assert len(flicks) == 10
    assert [f.id for f in flicks] == list(range(1, 11))
    m = s.metrics(now)
    assert m.flicks == 10
    assert m.overshoots == 4
    assert m.overshoot_rate == pytest.approx(0.4)
    assert m.correction_rate == pytest.approx(0.4)
    assert m.score == round(100 * (0.6 * 0.6 + 0.4 * 0.6))
    assert m.shots == 10 and m.taps == 10
    assert m.avg_amplitude == pytest.approx(30, abs=1)
    assert m.conversion == "calibrated"
    assert choose_drill(m).key == "overshoot"


def test_summary_with_few_flicks():
    s, _, now = session_with(3, 0)
    summary = summarize(s.metrics(now), START, 40.0, history=[])
    assert summary.metrics.score is None
    assert summary.drill is None
    assert (
        summary.message == "Not enough flicks yet (need 10) — no score or drill for this session."
    )


def test_score_without_drill_message():
    s, _, now = session_with(6, 0)
    summary = summarize(s.metrics(now), START, 40.0, history=[])
    assert summary.metrics.score == 100
    assert summary.drill is None
    assert summary.message == "Score is ready; play a bit longer for a drill suggestion."


def test_clean_session_drill():
    s, _, now = session_with(10, 0)
    m = s.metrics(now)
    assert m.score == 100
    assert choose_drill(m).key == "clean"


def test_metrics_when_empty():
    s = WarmupSession(CONV, START, t0=0.0)
    m = s.metrics(5.0)
    assert m.flicks == 0 and m.overshoot_rate == 0 and m.score is None
    assert m.elapsed_s == pytest.approx(5.0)
