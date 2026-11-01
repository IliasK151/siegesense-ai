"""Turns component state into the status lights shown in the app."""

from __future__ import annotations

from collections.abc import Callable

from .game_watcher import GameWatcher
from .profile import Profile
from .protocol import Light, StatusPayload

_NOT_YET = "Arrives in a later update"
_UNBUILT = {
    "capture": "Screen capture",
    "hud": "HUD reader",
    "coach": "Coach",
    "voice": "Voice",
}


# (available, reason when unavailable, currently tracking)
InputState = Callable[[], tuple[bool, str | None, bool]]


class StatusBoard:
    def __init__(
        self,
        watcher: GameWatcher,
        profile_getter: Callable[[], Profile | None],
        input_state: InputState | None = None,
    ) -> None:
        self._watcher = watcher
        self._profile_getter = profile_getter
        self._input_state = input_state or (lambda: (False, "Input tracking is not set up", False))

    def _input_light(self) -> Light:
        available, reason, active = self._input_state()
        if not available:
            return Light(
                state="warn",
                label="Input tracking unavailable",
                detail=reason or "Input tracking is not available.",
                fix="Run SiegeSense on Windows. If you are, restart the app.",
            )
        if active:
            return Light(
                state="ok",
                label="Tracking your mouse",
                detail="Reading your own mouse and keyboard. Nothing is sent to the game.",
            )
        return Light(
            state="ok",
            label="Input ready",
            detail="Your mouse will be read when you start Warm-up or calibration.",
        )

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
        lights = {"game": self._game_light(), "input": self._input_light()}
        for key, label in _UNBUILT.items():
            lights[key] = Light(state="off", label=label, detail=_NOT_YET)
        return StatusPayload(lights=lights)
