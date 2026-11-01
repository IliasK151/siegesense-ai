from conftest import TEST_FIXTURES

from siegesense_engine.input.events import Button, MouseMove
from siegesense_engine.input.source import ReplayInputSource
from siegesense_engine.mechanics.sensitivity import Conversion
from siegesense_engine.warmup import WarmupSession


def test_replay_fixture_has_twelve_flicks():
    from datetime import UTC, datetime

    source = ReplayInputSource(TEST_FIXTURES / "warmup_replay.jsonl")
    events = source._events  # the file as recorded
    conv = Conversion(12 * 0.02 * 0.0572957795, 12 * 0.02 * 0.0572957795, "estimated")
    s = WarmupSession(conv, datetime.now(UTC), t0=0.0)
    s.feed([e for e in events if isinstance(e, (MouseMove, Button))])
    s.poll(events[-1].t + 2)
    m = s.metrics(events[-1].t + 2)
    assert (m.flicks, m.overshoots) == (12, 5)
