import pytest
from hudsynth import render

from siegesense_engine.hud.killfeed import KillFeedReader, segment_lines, team_of
from siegesense_engine.hud.ocr import FakeOcr
from siegesense_engine.hud.regions import HudRegions, crop

R = HudRegions()
ME_KILLS = ("Ash.Main", "blue", "Thermite_1", "orange")
I_DIE = ("Bandit.X", "orange", "Ash.Main", "blue")


def feed(kills):
    return crop(render({"kills": kills}), R.killfeed)


def test_segment_lines_counts():
    assert len(segment_lines(feed([ME_KILLS]))) == 1
    assert len(segment_lines(feed([I_DIE, ME_KILLS]))) == 2
    assert segment_lines(feed([])) == []


@pytest.mark.ocr
def test_one_kill_line(ocr):
    reader = KillFeedReader(ocr, "Ash.Main")
    [e] = reader.read(feed([ME_KILLS]), t=1.0)
    assert reader.is_me(e.killer)
    assert e.victim.lower().startswith("thermite")
    assert (e.killer_team, e.victim_team) == ("blue", "orange")
    assert not reader.is_me(e.victim)
    assert e.headshot is None


@pytest.mark.ocr
def test_two_lines_order(ocr):
    reader = KillFeedReader(ocr, "Ash.Main")
    entries = reader.read(feed([I_DIE, ME_KILLS]), t=1.0)
    assert len(entries) == 2
    assert reader.is_me(entries[0].victim) and reader.is_me(entries[1].killer)
    assert entries[0].line_y < entries[1].line_y


def test_team_colours():
    img = feed([ME_KILLS])
    [(y0, y1)] = segment_lines(img)
    line = img[y0:y1]
    w = line.shape[1]
    assert team_of(line[:, : w // 2]) == "blue"
    assert team_of(line[:, w // 2 :]) == "orange"


def _fake_names():
    names = iter(["Ash.Main", "Thermite_1"] * 100)
    return FakeOcr(lambda img: (next(names), 0.95))


def test_entry_deduplicated():
    reader = KillFeedReader(_fake_names(), "Ash.Main")
    img = feed([ME_KILLS])
    got = []
    for t in (1.0, 2.0, 3.0, 4.0, 5.0):
        got += reader.read(img.copy(), t)
    assert len(got) == 1
    reader.reset_change_detection()
    assert len(reader.read(img.copy(), 16.0)) == 1  # same pair again after 10 s is a new kill


def test_fuzzy_own_name():
    reader = KillFeedReader(_fake_names(), "Ash.Main")
    assert reader.is_me("Ash.Maln")
    assert reader.is_me("ash.main")
    assert not reader.is_me("Ash")
    assert not reader.is_me("Bandit.X")


def test_unchanged_crop_skips_ocr():
    ocr = _fake_names()
    reader = KillFeedReader(ocr, "Ash.Main")
    img = feed([ME_KILLS])
    reader.read(img, 1.0)
    calls = ocr.calls
    reader.read(img.copy(), 1.1)
    reader.read(img.copy(), 1.2)
    assert ocr.calls == calls


def test_empty_feed():
    reader = KillFeedReader(_fake_names(), "Ash.Main")
    assert reader.read(feed([]), 1.0) == []
