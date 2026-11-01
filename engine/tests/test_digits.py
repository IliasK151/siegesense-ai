import numpy as np
import pytest
from hudsynth import render

from siegesense_engine.hud.digits import read_health, read_score, read_timer
from siegesense_engine.hud.regions import HudRegions, crop

R = HudRegions()
pytestmark = pytest.mark.ocr


def frame(**state):
    return render({"timer": None, "score": None, "health": None, "kills": [], **state})


@pytest.mark.parametrize("seconds", [165, 7, 45, 180])
def test_read_timer_values(ocr, seconds):
    r = read_timer(crop(frame(timer=seconds), R.timer), ocr)
    assert r.value == seconds
    assert r.confidence > 0.5


@pytest.mark.parametrize("score", [(0, 0), (2, 1), (4, 3)])
def test_read_score(ocr, score):
    img = frame(score=score)
    assert read_score(crop(img, R.score_left), ocr).value == score[0]
    assert read_score(crop(img, R.score_right), ocr).value == score[1]


@pytest.mark.parametrize("hp", [100, 87, 5, 120])
def test_read_health(ocr, hp):
    assert read_health(crop(frame(health=hp), R.health), ocr).value == hp


def test_health_missing_when_dead(ocr):
    r = read_health(crop(frame(health=None), R.health), ocr)
    assert r.value is None


def test_timer_garbage_low_confidence(ocr):
    noise = np.random.default_rng(1).integers(0, 255, (48, 115, 3), np.uint8)
    r = read_timer(noise, ocr)
    assert r.value is None
    assert r.confidence < 0.5


def test_timer_rejects_impossible_values():
    from siegesense_engine.hud.digits import parse_timer

    assert parse_timer("2:45") == 165
    assert parse_timer("245") == 165
    assert parse_timer("2.45") == 165
    assert parse_timer("0:07") == 7
    assert parse_timer("12:00") is None
    assert parse_timer("2:75") is None
    assert parse_timer("abc") is None
