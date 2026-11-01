import pytest

from siegesense_engine.input.events import VK
from siegesense_engine.mechanics.habits import HabitTracker


def shoot(h, t, hold):
    h.button(t, "left", True)
    h.button(t + hold, "left", False)


def test_tap_burst_spray_classification():
    h = HabitTracker()
    shoot(h, 0.0, 0.08)
    shoot(h, 1.0, 0.3)
    shoot(h, 2.0, 0.9)
    s = h.snapshot()
    assert (s.shots, s.taps, s.bursts, s.sprays) == (3, 1, 1, 1)


def test_moving_shot():
    h = HabitTracker()
    h.key(0.0, VK.A, True)
    shoot(h, 0.1, 0.05)
    h.key(0.2, VK.A, False)
    shoot(h, 0.5, 0.05)
    s = h.snapshot()
    assert s.shots == 2 and s.moving_shots == 1


def test_strafe_switch():
    h = HabitTracker()
    h.key(0.0, VK.A, True)
    h.key(0.2, VK.A, False)
    h.key(0.3, VK.D, True)  # switch within 500 ms
    h.key(0.4, VK.D, False)
    h.key(0.6, VK.A, True)  # switch again
    h.key(0.7, VK.A, False)
    h.key(2.0, VK.D, True)  # too late, not a switch
    assert h.snapshot().strafe_switches == 2


def test_key_repeat_is_not_a_new_press():
    h = HabitTracker()
    h.key(0.0, VK.A, True)
    h.key(0.03, VK.A, True)  # auto-repeat
    shoot(h, 0.05, 0.05)
    h.key(0.1, VK.A, False)
    s = h.snapshot()
    assert s.moving_shots == 1 and s.strafe_switches == 0


def test_crouch_spam_counts_once_per_run():
    h = HabitTracker()
    for i in range(5):
        h.key(i * 0.3, VK.C, True)
        h.key(i * 0.3 + 0.1, VK.C, False)
    h.key(10.0, VK.C, True)
    assert h.snapshot().crouch_spams == 1


def test_ads_seconds():
    h = HabitTracker()
    h.button(1.0, "right", True)
    h.button(3.5, "right", False)
    assert h.snapshot().ads_seconds == pytest.approx(2.5)


def test_ads_seconds_includes_open_hold():
    h = HabitTracker()
    h.button(1.0, "right", True)
    h.move(2.0, 0.1, 0)
    assert h.snapshot().ads_seconds == pytest.approx(1.0)


def _wiggle(h, t0, amp, n=10):
    for i in range(n):
        h.move(t0 + i * 0.05 + 0.01, amp if i % 2 == 0 else -amp, 0)


def test_ads_jitter():
    h = HabitTracker()
    h.button(0.0, "right", True)
    _wiggle(h, 0.0, 0.3)
    h.button(0.6, "right", False)
    assert h.snapshot().ads_jitter == 9


def test_jitter_ignores_big_moves():
    h = HabitTracker()
    h.button(0.0, "right", True)
    _wiggle(h, 0.0, 1.5)
    h.button(0.6, "right", False)
    assert h.snapshot().ads_jitter == 0


def test_no_jitter_when_not_ads():
    h = HabitTracker()
    _wiggle(h, 0.0, 0.3)
    assert h.snapshot().ads_jitter == 0
