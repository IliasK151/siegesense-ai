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


# --- Live Mode fixtures --------------------------------------------------------------------
from siegesense_engine.hud.reader import HudCheckResult, ReaderResult  # noqa: E402
from siegesense_engine.hud.regions import HudRegions  # noqa: E402
from siegesense_engine.live import DeathInfo, LiveEventOut, MatchSummary  # noqa: E402
from siegesense_engine.rounds import RoundSummary  # noqa: E402

death = LiveEventOut(
    kind="death", t=1234.5, round=3, confidence="ok", clip="20261101-183000-r3-death.mp4",
    data={"killer": "Bandit.X", "time_alive_s": 41.2, "first_death": True},
)  # fmt: skip
rnd = RoundSummary(
    number=3, phase_seen=["prep", "action"], started_t=1193.3, ended_t=1260.0, result="loss",
    kills=1, died=True, death_confidence="ok", time_alive_s=41.2, first_blood=False,
    first_death=True, traded=False, traded_teammate=0, repeeks=1,
)  # fmt: skip
check = HudCheckResult(
    image_jpeg_b64="/9j/4AAQSkZJRgABAQ==", width=960, height=540, regions=HudRegions(),
    readers=[
        ReaderResult(key="timer", text="2:45", confidence=0.98, ok=True),
        ReaderResult(key="score_left", text="2", confidence=0.97, ok=True),
        ReaderResult(key="score_right", text="1", confidence=0.97, ok=True),
        ReaderResult(key="health", text="87", confidence=0.96, ok=True),
        ReaderResult(key="killfeed", text="Ash.Main → Thermite_1", confidence=0.93, ok=True),
    ],
)  # fmt: skip
match = MatchSummary(
    id=4, started_at="2026-11-01T18:30:00+00:00", ended_at="2026-11-01T19:05:00+00:00",
    rounds=[rnd],
    deaths=[DeathInfo(round=3, killer="Bandit.X", time_alive_s=41.2, confidence="ok",
                      clip="20261101-183000-r3-death.mp4")],
)  # fmt: skip
(out / "live_event.json").write_text(json.dumps(env("live_event", death.model_dump()), indent=1))
(out / "round_summary.json").write_text(
    json.dumps(env("round_summary", rnd.model_dump()), indent=1)
)
(out / "hud_check.json").write_text(
    json.dumps(env("response", {"ok": True, "data": check.model_dump()}, id="11"), indent=1)
)
(out / "match_summary.json").write_text(
    json.dumps(env("response", {"ok": True, "data": match.model_dump()}, id="12"), indent=1)
)
