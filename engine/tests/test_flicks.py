import pytest
from synth import end_time, flick

from siegesense_engine.mechanics.flicks import FlickDetector


def run(samples, shots=(), poll_at=None):
    det = FlickDetector()
    for t, dx, dy in samples:
        det.move(t, dx, dy)
    for s in shots:
        det.shot(s)
    return det.poll(poll_at if poll_at is not None else end_time(samples) + 1.0)


def test_clean_flick():
    [f] = run(flick(1.0, 30, 0.12))
    assert f.amplitude == pytest.approx(30, abs=1)
    assert f.peak_speed == pytest.approx(469, abs=30)
    assert not f.corrected and not f.overshoot
    assert f.direction == pytest.approx(0, abs=2)


def test_overshoot_with_shot():
    samples = flick(1.0, 30, 0.12, overshoot=6)
    [f] = run(samples, shots=[end_time(samples) + 0.1])
    assert f.corrected
    assert f.reversal == pytest.approx(6, abs=0.7)
    assert f.overshoot
    assert f.shot


def test_correction_without_shot():
    [f] = run(flick(1.0, 30, 0.12, overshoot=6))
    assert f.corrected and not f.overshoot and not f.shot


def test_small_reversal_not_corrected():
    [f] = run(flick(1.0, 30, 0.12, overshoot=2))
    assert not f.corrected


def test_slow_pan_not_flick():
    assert run(flick(1.0, 30, 0.5)) == []


def test_small_twitch_not_flick():
    assert run(flick(1.0, 3, 0.014)) == []


def test_two_flicks():
    samples = flick(1.0, 30, 0.12) + flick(2.0, 20, 0.1, angle_deg=180)
    flicks = run(samples)
    assert len(flicks) == 2
    assert flicks[1].direction == pytest.approx(180, abs=2) or flicks[1].direction == pytest.approx(
        -180, abs=2
    )


def test_direction_up_left():
    [f] = run(flick(1.0, 30, 0.12, angle_deg=135))
    assert f.direction == pytest.approx(135, abs=3)


def test_high_rate_mouse_same_result():
    [slow] = run(flick(1.0, 30, 0.12, rate_hz=1000))
    [fast] = run(flick(1.0, 30, 0.12, rate_hz=8000))
    assert fast.amplitude == pytest.approx(slow.amplitude, abs=0.5)


def test_poll_waits_for_shot_window():
    det = FlickDetector()
    samples = flick(1.0, 30, 0.12)
    for t, dx, dy in samples:
        det.move(t, dx, dy)
    peak = 1.06
    assert det.poll(peak + 0.1) == []
    assert len(det.poll(peak + 0.7)) == 1
    assert det.poll(peak + 2.0) == []  # reported once


def test_trace_shape():
    [f] = run(flick(1.0, 30, 0.12, overshoot=6))
    assert f.trace[0][0] == 0
    assert f.trace[-1][1] == pytest.approx(24, abs=1)
    assert max(p for _, p in f.trace) == pytest.approx(30, abs=1)


def test_duration_reported():
    [f] = run(flick(1.0, 30, 0.12))
    assert 80 <= f.duration_ms <= 140


def test_onset_ignores_stale_history_after_idle():
    # a tiny movement, 10 s idle, then a Raw Input burst (8° in one bin) into a 20° flick
    samples = [(0.1, 0.2, 0.0), (10.2, 8.0, 0.0)] + flick(10.205, 20, 0.1)
    flicks = run(samples)
    assert flicks
    for f in flicks:
        assert f.duration_ms < 400
        assert f.trace[-1][0] < 700  # onset .. peak + 250 ms, never the 10 s idle gap


def test_reversal_measured_from_furthest_point():
    # 30° flick, slow forward drift of 2.5°, then a 4° pull-back (13% of the flick)
    samples = flick(1.0, 30, 0.12)
    t = end_time(samples)
    samples += [(t + 0.001 * (i + 1), 2.5 / 40, 0.0) for i in range(40)]  # 62 °/s drift
    t = end_time(samples)
    samples += flick(t, -4, 0.05)
    [f] = run(samples)
    assert f.reversal == pytest.approx(4, abs=0.5)
    assert f.corrected
