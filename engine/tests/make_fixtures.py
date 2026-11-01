"""Regenerates the warm-up protocol fixtures. Run from engine/: python tests/make_fixtures.py"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, "tests")
from synth import end_time, flick, to_counts

from siegesense_engine.calibration import CalibrationState
from siegesense_engine.input.events import Button
from siegesense_engine.mechanics.sensitivity import Conversion
from siegesense_engine.warmup import HistoryPoint, WarmupSession, summarize

conv = Conversion(0.0137509871, 0.0137509871, "estimated")
start = datetime(2026, 11, 1, 18, 30, tzinfo=UTC)
s = WarmupSession(conv, start, t0=0.0)
flicks = []
t = 1.0
for i in range(12):
    samples = flick(
        t, 30 + i, 0.12, angle_deg=0 if i % 2 == 0 else 180, overshoot=6 if i < 5 else 0
    )
    shot = end_time(samples) + 0.1
    s.feed(
        to_counts(samples, conv.yaw)
        + [Button(shot, "left", True), Button(shot + 0.08, "left", False)]
    )
    flicks += s.poll(t + 0.9)
    t += 1.2
flicks += s.poll(t + 2)
m = s.metrics(t)
hist = [HistoryPoint(started_at="2026-10-31T18:00:00+00:00", score=58)]
summary = summarize(m, start, t, hist)
summary.id = 2
summary.history = hist + [HistoryPoint(started_at=summary.started_at, score=m.score)]
f0 = flicks[0].model_dump()
f0["trace"] = f0["trace"][::4]
cal = CalibrationState(phase="measuring", runs=[31416], current_counts=12045, warning=None)
out = Path("../protocol/fixtures")


def env(type, payload, id=None):
    e = {"type": type, "ts": 1000, "payload": payload}
    if id:
        e["id"] = id
    return e


(out / "metrics.json").write_text(json.dumps(env("metrics", m.model_dump()), indent=1))
(out / "flick.json").write_text(json.dumps(env("flick", f0)))
(out / "calibration.json").write_text(json.dumps(env("calibration", cal.model_dump()), indent=1))
(out / "warmup_summary.json").write_text(
    json.dumps(env("response", {"ok": True, "data": summary.model_dump()}, id="9"), indent=1)
)
print(m.flicks, m.overshoots, m.score, summary.drill.key)
