from synth import end_time, flick, to_counts

from siegesense_engine.coach.mechanics import LiveMechanics
from siegesense_engine.input.events import VK, Button, Key
from siegesense_engine.mechanics.sensitivity import Conversion

CONV = Conversion(0.05, 0.05, "estimated")


def test_live_mechanics_counts_flicks_and_moving_shots():
    m = LiveMechanics(CONV)
    t = 1.0
    for i in range(4):
        samples = flick(t, 30, 0.12, overshoot=6 if i < 2 else 0)
        shot = end_time(samples) + 0.1
        events = to_counts(samples, CONV.yaw) + [
            Button(shot, "left", True),
            Button(shot + 0.05, "left", False),
        ]
        if i == 3:
            events = [Key(shot - 0.2, VK.D, True)] + events + [Key(shot + 0.2, VK.D, False)]
        m.feed(events)
        t += 1.2
    m.poll(t + 2)
    s = m.stats()
    assert s.flicks == 4 and s.overshoots == 2
    assert s.overshoot_rate == 0.5
    assert s.shots == 4 and s.moving_shots == 1 and s.moving_shot_rate == 0.25


def test_crouch_marker_deltas():
    m = LiveMechanics(CONV)
    before = m.round_marker()
    m.feed([Key(0.1 * i, VK.C, d) for i, d in enumerate([True, False] * 4)])
    assert m.round_marker() - before == 1
