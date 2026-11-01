from siegesense_engine.hud.reader import HudReading, KillEntryModel
from siegesense_engine.rounds import RoundTracker

ME = "Ash.Main"


def kill(killer, victim, kt, vt):
    return KillEntryModel(
        killer=killer, victim=victim, killer_team=kt, victim_team=vt,
        killer_is_me=killer == ME, victim_is_me=victim == ME, headshot=None, confidence=0.9,
    )  # fmt: skip


def reading(t, timer, score=(0, 0), health=100, kills=()):
    return HudReading(
        t=t, timer=timer, timer_conf=0.9 if timer is not None else 0.0,
        score_mine=score[0], score_theirs=score[1], health=health, health_conf=0.9,
        kills=list(kills), confidence="ok",
    )  # fmt: skip


class Script:
    """Feeds one reading per 0.1 s; collects events."""

    def __init__(self):
        self.rt = RoundTracker(ME)
        self.t = 0.0
        self.events = []

    def run(self, seconds, timer_fn, **kw):
        end = self.t + seconds
        while self.t < end - 1e-9:
            self.events += self.rt.hud(reading(self.t, timer_fn(self.t), **kw))
            kw.pop("kills", None)  # kill-feed entries are only "new" once
            self.t = round(self.t + 0.1, 3)

    def kinds(self):
        return [e.kind for e in self.events]


def countdown(start, t0):
    return lambda t: max(0, int(start - (t - t0)))


def test_round_lifecycle():
    s = Script()
    s.run(3, countdown(45, 0))  # prep
    s.run(3, countdown(180, s.t))  # action
    s.run(1, lambda t: None, score=(1, 0))  # round over: we scored
    assert s.kinds()[:3] == ["round_start", "phase", "phase"]
    assert s.events[1].data == {"phase": "prep"} and s.events[2].data == {"phase": "action"}
    [end] = [e for e in s.events if e.kind == "round_end"]
    assert end.data["result"] == "win"
    [r] = s.rt.rounds()
    assert r.number == 1 and r.result == "win" and not r.died


def test_new_round_after_previous():
    s = Script()
    s.run(2, countdown(180, 0))
    s.run(1, lambda t: None, score=(0, 1))
    s.run(2, countdown(45, s.t), score=(0, 1))
    assert [r.number for r in s.rt.rounds()] == [1, 2]
    assert s.rt.rounds()[0].result == "loss"


def test_death_confirmed_two_signals():
    s = Script()
    s.run(2, countdown(180, 0))
    s.run(0.1, countdown(178, s.t), kills=[kill("Bandit.X", ME, "orange", "blue")])
    s.run(2, countdown(178, s.t), health=None)
    [d] = [e for e in s.events if e.kind == "death"]
    assert d.confidence == "ok"
    assert d.data["killer"] == "Bandit.X"
    assert 1.9 <= d.data["time_alive_s"] <= 2.2
    r = s.rt.rounds()[0]
    assert r.died and r.first_death


def test_death_kill_feed_only_low():
    s = Script()
    s.run(2, countdown(180, 0))
    s.run(0.1, countdown(178, s.t), kills=[kill("Bandit.X", ME, "orange", "blue")])
    s.run(5, countdown(178, s.t))  # health still showing
    [d] = [e for e in s.events if e.kind == "death"]
    assert d.confidence == "low"


def test_first_blood():
    s = Script()
    s.run(1, countdown(180, 0))
    s.run(0.1, countdown(179, s.t), kills=[kill(ME, "Thermite_1", "blue", "orange")])
    s.run(0.5, countdown(179, s.t), kills=[kill("Bandit.X", "Sledge", "orange", "blue")])
    r = s.rt.rounds()[0]
    assert r.first_blood and r.kills == 1 and not r.first_death
    assert [e.kind for e in s.events].count("kill") == 1


def test_traded_death():
    s = Script()
    s.run(1, countdown(180, 0))
    s.run(0.1, countdown(179, s.t), kills=[kill("Bandit.X", ME, "orange", "blue")])
    s.run(2, countdown(179, s.t), health=None)
    s.run(
        0.1, countdown(177, s.t), health=None, kills=[kill("Sledge", "Bandit.X", "blue", "orange")]
    )
    assert s.rt.rounds()[0].traded


def test_traded_teammate():
    s = Script()
    s.run(1, countdown(180, 0))
    s.run(0.1, countdown(179, s.t), kills=[kill("Bandit.X", "Sledge", "orange", "blue")])
    s.run(2, countdown(179, s.t))
    s.run(0.1, countdown(177, s.t), kills=[kill(ME, "Bandit.X", "blue", "orange")])
    assert s.rt.rounds()[0].traded_teammate == 1


def test_repeek():
    s = Script()
    s.rt.input(0.0, 0.0)
    s.run(1, countdown(180, 0))
    s.run(0.1, countdown(179, s.t), kills=[kill(ME, "Thermite_1", "blue", "orange")])
    t_kill = s.t
    s.rt.input(t_kill + 0.3, 25.0)  # swing away
    s.rt.input(t_kill + 1.2, 1.5)  # back on the same angle
    s.run(0.5, countdown(178, s.t))
    assert "repeek" in s.kinds()
    assert s.rt.rounds()[0].repeeks == 1


def test_no_repeek_without_moving_away():
    s = Script()
    s.rt.input(0.0, 0.0)
    s.run(1, countdown(180, 0))
    s.run(0.1, countdown(179, s.t), kills=[kill(ME, "Thermite_1", "blue", "orange")])
    s.rt.input(s.t + 0.5, 2.0)
    s.run(4, countdown(178, s.t))
    assert "repeek" not in s.kinds()


def test_no_false_death_on_teammate_kill():
    s = Script()
    s.run(1, countdown(180, 0))
    s.run(0.1, countdown(179, s.t), kills=[kill("Bandit.X", "Sledge", "orange", "blue")])
    s.run(5, countdown(179, s.t), health=None)  # e.g. health unreadable for a moment
    assert "death" not in s.kinds()


def test_single_timer_misread_is_ignored():
    s = Script()
    s.run(2, countdown(150, 0))
    s.run(0.1, lambda t: 170)  # OCR misread 2:30 → 2:50 for one frame
    s.run(2, countdown(148, s.t))
    assert [r.number for r in s.rt.rounds()] == [1]
    assert "round_end" not in s.kinds()


def test_single_score_misread_is_ignored():
    s = Script()
    s.run(2, countdown(150, 0), score=(2, 1))
    s.run(0.1, countdown(148, s.t), score=(3, 1))  # one bad read
    s.run(2, countdown(148, s.t), score=(2, 1))
    assert "round_end" not in s.kinds()


def test_score_change_confirmed_by_two_readings():
    s = Script()
    s.run(2, countdown(150, 0), score=(2, 1))
    s.run(1, lambda t: None, score=(3, 1))
    assert s.rt.rounds()[0].result == "win"


def test_post_plant_death_still_counts():
    s = Script()
    s.run(2, countdown(60, 0))  # action
    s.run(10, lambda t: None)  # bomb planted: timer replaced by the defuser icon
    s.run(0.1, lambda t: None, kills=[kill("Bandit.X", ME, "orange", "blue")])
    s.run(2, lambda t: None, health=None)
    assert "round_end" not in s.kinds()
    deaths = [e for e in s.events if e.kind == "death"]
    assert len(deaths) == 1 and deaths[0].confidence == "ok"
    s.run(1, lambda t: None, health=None, score=(0, 1))
    assert s.rt.rounds()[0].result == "loss" and s.rt.rounds()[0].died


def test_defuser_countdown_is_not_a_new_round():
    s = Script()
    s.run(2, countdown(30, 0))  # action, 0:30 left
    s.run(3, countdown(45, s.t))  # plant: 0:45 defuser countdown appears
    assert [r.number for r in s.rt.rounds()] == [1]


def test_short_name_with_one_ocr_error_is_me():
    rt = RoundTracker("Bob")
    s = Script()
    s.rt = rt
    s.run(1, countdown(150, 0))
    k = KillEntryModel(
        killer="B0b",
        victim="Thermite",
        killer_team="blue",
        victim_team="orange",
        killer_is_me=True,
        victim_is_me=False,
        headshot=None,
        confidence=0.9,
    )
    s.run(0.1, countdown(149, s.t), kills=[k])
    assert rt.rounds()[0].kills == 1


def test_same_victim_counted_once_per_round():
    s = Script()
    s.run(1, countdown(150, 0))
    s.run(0.1, countdown(149, s.t), kills=[kill(ME, "Thermite_1", "blue", "orange")])
    s.run(0.5, countdown(149, s.t))
    s.run(0.1, countdown(148, s.t), kills=[kill(ME, "Thermite_l", "blue", "orange")])  # OCR flicker
    assert s.rt.rounds()[0].kills == 1
