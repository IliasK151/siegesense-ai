from siegesense_engine.calibration import CalibrationSession
from siegesense_engine.input.events import VK, Key, MouseMove


def f8(t, down=True):
    return Key(t, VK.F8, down)


def run(counts: int, t0: float, step: int = 100):
    events = [f8(t0), f8(t0 + 0.05, False)]
    n = abs(counts) // step
    sign = 1 if counts > 0 else -1
    events += [MouseMove(t0 + 0.1 + i * 0.001, sign * step, 0) for i in range(n)]
    t_end = t0 + 0.2 + n * 0.001
    events += [f8(t_end), f8(t_end + 0.05, False)]
    return events


def test_three_runs_median():
    c = CalibrationSession()
    c.feed(run(31400, 0) + run(31600, 10) + run(31500, 20))
    s = c.state()
    assert s.phase == "done"
    assert s.runs == [31400, 31600, 31500]
    assert s.result == 31500
    assert s.spread == (31600 - 31400) / 31500
    assert s.warning is None


def test_live_counter_while_measuring():
    c = CalibrationSession()
    assert c.state().phase == "armed"
    changed = c.feed([f8(0), f8(0.05, False), MouseMove(0.1, 500, 3)])
    assert changed
    s = c.state()
    assert s.phase == "measuring" and s.current_counts == 500


def test_tiny_run_rejected():
    c = CalibrationSession()
    c.feed(run(800, 0))
    s = c.state()
    assert s.runs == [] and s.phase == "armed"
    assert s.warning == "That was too small — turn one full circle, then press F8."


def test_key_repeat_ignored():
    c = CalibrationSession()
    c.feed([f8(0), f8(0.03), f8(0.06), MouseMove(0.1, 5000, 0)])
    assert c.state().phase == "measuring"
    assert c.state().current_counts == 5000


def test_spread_warning():
    c = CalibrationSession()
    c.feed(run(30000, 0) + run(31500, 10) + run(33000, 20))
    s = c.state()
    assert s.phase == "done"
    assert s.warning == "Your runs differ by 10% — try again slowly for a more exact result."


def test_left_turn_counts_positive():
    c = CalibrationSession(target_runs=1)
    c.feed(run(-31500, 0))
    assert c.state().runs == [31500]


def test_cancel():
    c = CalibrationSession()
    c.feed(run(31500, 0))
    c.cancel()
    s = c.state()
    assert s.phase == "cancelled"
    assert not c.feed(run(31500, 10))
