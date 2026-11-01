import base64

import pytest
from hudsynth import render

from siegesense_engine.capture.frames import Frame
from siegesense_engine.hud.reader import HudReader
from siegesense_engine.hud.regions import Box, HudRegions

pytestmark = pytest.mark.ocr
STATE = {
    "timer": 165,
    "score": (2, 1),
    "health": 87,
    "kills": [("Ash.Main", "blue", "Thermite_1", "orange")],
}


def test_full_reading(ocr):
    reader = HudReader(ocr, HudRegions(), "Ash.Main", "left")
    r = reader.read(Frame(1.0, render(STATE)))
    assert r.timer == 165
    assert (r.score_mine, r.score_theirs) == (2, 1)
    assert r.health == 87
    assert len(r.kills) == 1 and r.kills[0].killer_is_me and not r.kills[0].victim_is_me
    assert r.kills[0].killer_team == "blue"
    assert r.confidence == "ok"


def test_my_score_side_right(ocr):
    reader = HudReader(ocr, HudRegions(), "Ash.Main", "right")
    r = reader.read(Frame(1.0, render(STATE)))
    assert (r.score_mine, r.score_theirs) == (1, 2)


def test_dead_has_no_health(ocr):
    reader = HudReader(ocr, HudRegions(), "Ash.Main", "left")
    r = reader.read(Frame(1.0, render({**STATE, "health": None})))
    assert r.health is None and r.timer == 165


def test_wrong_region_low_confidence(ocr):
    shifted = HudRegions(
        timer=Box(x=0.2, y=0.5, w=0.06, h=0.045),
        score_left=Box(x=0.1, y=0.5, w=0.04, h=0.045),
        score_right=Box(x=0.3, y=0.5, w=0.04, h=0.045),
    )
    reader = HudReader(ocr, shifted, "Ash.Main", "left")
    frame = render(STATE)
    readings = [reader.read(Frame(i * 0.1, frame)) for i in range(12)]
    assert readings[0].confidence == "ok"  # not judged yet
    assert readings[-1].confidence == "low"


def test_snapshot_contents(ocr):
    reader = HudReader(ocr, HudRegions(), "Ash.Main", "left")
    snap = reader.snapshot(Frame(1.0, render(STATE)))
    jpeg = base64.b64decode(snap.image_jpeg_b64)
    assert jpeg[:2] == b"\xff\xd8"
    assert snap.width == 960
    assert snap.regions == HudRegions()
    by_key = {r.key: r for r in snap.readers}
    assert by_key["timer"].text == "2:45" and by_key["timer"].ok
    assert by_key["health"].text == "87"
    assert "Ash.Main" in by_key["killfeed"].text
