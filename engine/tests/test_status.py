from types import SimpleNamespace

import psutil

from siegesense_engine.game_watcher import FakeGameWatcher, GameState, PsutilGameWatcher
from siegesense_engine.profile import Profile
from siegesense_engine.status import StatusBoard


def profile(window_mode="borderless") -> Profile:
    return Profile(
        in_game_name="Ash.Main",
        dpi=800,
        yaw_sensitivity=10,
        pitch_sensitivity=10,
        window_mode=window_mode,
    )


def board(running=False, focused=False, prof=None) -> StatusBoard:
    return StatusBoard(FakeGameWatcher(GameState(running, focused)), lambda: prof)


def test_game_not_running_warns():
    game = board().compute().lights["game"]
    assert game.state == "warn"
    assert game.fix == "Launch Rainbow Six Siege"


def test_fullscreen_warns_with_fix():
    game = board(running=True, focused=True, prof=profile("fullscreen")).compute().lights["game"]
    assert game.state == "warn"
    assert "Borderless" in game.fix


def test_running_focused_ok():
    game = board(running=True, focused=True, prof=profile()).compute().lights["game"]
    assert game.state == "ok"
    assert game.label == "Siege running"


def test_running_background_ok():
    game = board(running=True, focused=False).compute().lights["game"]
    assert game.state == "ok"
    assert "background" in game.label


def test_every_light_present():
    lights = board().compute().lights
    assert set(lights) == {"game", "input", "capture", "hud", "coach", "voice"}


def _procs(*names):
    return lambda attrs=None: [
        SimpleNamespace(info={"name": n, "pid": i}) for i, n in enumerate(names)
    ]


def test_psutil_watcher_not_running(monkeypatch):
    monkeypatch.setattr(psutil, "process_iter", _procs("chrome.exe", None))
    assert PsutilGameWatcher().poll().running is False


def test_psutil_watcher_running(monkeypatch):
    monkeypatch.setattr(psutil, "process_iter", _procs("chrome.exe", "rainbowsix.EXE"))
    assert PsutilGameWatcher().poll().running is True


def test_input_light_states():
    def light(available, reason, active):
        b = StatusBoard(FakeGameWatcher(), lambda: None, lambda: (available, reason, active))
        return b.compute().lights["input"]

    off = light(False, "Input tracking works on Windows only", False)
    assert off.state == "warn" and off.detail == "Input tracking works on Windows only"
    assert off.fix
    assert light(True, None, False).label == "Input ready"
    assert light(True, None, True).label == "Tracking your mouse"
