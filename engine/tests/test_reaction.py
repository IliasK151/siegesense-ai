import numpy as np
import pytest

from siegesense_engine.reaction import ReactionTimer

DARK = np.full((64, 64), 30, np.uint8)
BRIGHT = DARK.copy()
BRIGHT[20:44, 20:44] = 220  # a target pops up in the middle


def test_reaction_measured():
    r = ReactionTimer()
    r.frame(1.00, DARK)
    r.frame(1.03, BRIGHT)  # stimulus; mouse has been still
    r.flick_onset(1.25)
    assert r.samples() == [pytest.approx(220, abs=1)]


def test_ignored_when_mouse_moving():
    r = ReactionTimer()
    r.frame(1.00, DARK)
    r.moved(0.95, 2.0)  # moving 80 ms before the change
    r.frame(1.03, BRIGHT)
    r.flick_onset(1.25)
    assert r.samples() == []


def test_no_flick_within_1s_ignored():
    r = ReactionTimer()
    r.frame(1.00, DARK)
    r.frame(1.03, BRIGHT)
    r.flick_onset(2.2)
    assert r.samples() == []


def test_small_change_is_not_a_stimulus():
    r = ReactionTimer()
    r.frame(1.00, DARK)
    r.frame(1.03, DARK + 3)
    r.flick_onset(1.25)
    assert r.samples() == []


def test_one_sample_per_stimulus():
    r = ReactionTimer()
    r.frame(1.00, DARK)
    r.frame(1.03, BRIGHT)
    r.flick_onset(1.25)
    r.flick_onset(1.6)
    assert len(r.samples()) == 1


def test_median():
    r = ReactionTimer()
    for i, delay in enumerate([0.2, 0.25, 0.3]):
        base = 10 + i * 3
        r.frame(base, DARK)
        r.frame(base + 0.03, BRIGHT)
        r.flick_onset(base + 0.03 + delay)
        r.frame(base + 1.5, DARK)
    assert r.median_ms() == pytest.approx(250, abs=1)
