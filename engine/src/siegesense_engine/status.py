"""Turns component state into the status lights shown in the app."""

from __future__ import annotations

from collections.abc import Callable

from .game_watcher import GameWatcher
from .profile import Profile
from .protocol import Light, StatusPayload

_NOT_YET = "Arrives in a later update"
_UNBUILT = {
    "capture": "Screen capture",
    "input": "Input tracking",
    "hud": "HUD reader",
    "coach": "Coach",
    "voice": "Voice",
}


class StatusBoard:
    def __init__(self, watcher: GameWatcher, profile_getter: Callable[[], Profile | None]) -> None:
        self._watcher = watcher
        self._profile_getter = profile_getter

    def _game_light(self) -> Light:
        state = self._watcher.poll()
        if not state.running:
            return Light(
                state="warn",
                label="Siege not running",
                detail="Rainbow Six Siege was not detected.",
                fix="Launch Rainbow Six Siege",
            )
        profile = self._profile_getter()
        if profile is not None and profile.window_mode == "fullscreen":
            return Light(
                state="warn",
                label="Exclusive fullscreen",
                detail="Siege is set to exclusive fullscreen, which hides the in-game overlay.",
                fix="Switch Siege to Borderless in Display settings so the overlay can show",
            )
        if not state.focused:
            return Light(
                state="ok",
                label="Siege running (in background)",
                detail="Siege is running but not the active window.",
            )
        return Light(state="ok", label="Siege running", detail="Siege is running and focused.")

    def compute(self) -> StatusPayload:
        lights = {"game": self._game_light()}
        for key, label in _UNBUILT.items():
            lights[key] = Light(state="off", label=label, detail=_NOT_YET)
        return StatusPayload(lights=lights)
