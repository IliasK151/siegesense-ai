"""Turns component state into the status lights shown in the app."""

from __future__ import annotations

from collections.abc import Callable

from .game_watcher import GameWatcher
from .profile import Profile
from .protocol import Light, StatusPayload

_NOT_YET = "Arrives in a later update"
_UNBUILT = {
    "coach": "Coach",
    "voice": "Voice",
}


# (available, reason when unavailable, currently tracking)
InputState = Callable[[], tuple[bool, str | None, bool]]
# (available, reason, active, fps target, behind)
CaptureState = Callable[[], tuple[bool, str | None, bool, int, bool]]
# (live, hud confidence low)
HudState = Callable[[], tuple[bool, bool]]


class StatusBoard:
    def __init__(
        self,
        watcher: GameWatcher,
        profile_getter: Callable[[], Profile | None],
        input_state: InputState | None = None,
        capture_state: CaptureState | None = None,
        hud_state: HudState | None = None,
    ) -> None:
        self._watcher = watcher
        self._profile_getter = profile_getter
        self._input_state = input_state or (lambda: (False, "Input tracking is not set up", False))
        self._capture_state = capture_state or (
            lambda: (False, "Screen capture is not set up", False, 30, False)
        )
        self._hud_state = hud_state or (lambda: (False, False))

    def _capture_light(self) -> Light:
        available, reason, active, fps, behind = self._capture_state()
        if not available:
            return Light(
                state="warn",
                label="Capture unavailable",
                detail=reason or "Screen capture is not available.",
                fix="Run SiegeSense on Windows with Siege in Borderless or Windowed mode.",
            )
        if not active:
            return Light(state="off", label="Screen capture", detail="Starts with Live Mode.")
        if behind:
            return Light(
                state="warn",
                label="Falling behind",
                detail=f"Your PC is busy, so capture was lowered to {fps} fps.",
                fix="Close other heavy apps, or lower Siege's graphics settings.",
            )
        return Light(state="ok", label=f"Capturing {fps} fps", detail="Reading your screen.")

    def _hud_light(self) -> Light:
        live, low = self._hud_state()
        if not live:
            return Light(state="off", label="HUD reader", detail="Starts with Live Mode.")
        if low:
            return Light(
                state="warn",
                label="Can't find the HUD",
                detail="The timer and score aren't where SiegeSense is looking.",
                fix="Open Settings → HUD check and move the boxes onto your HUD.",
            )
        return Light(state="ok", label="Reading HUD", detail="Kill feed, timer and score found.")

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
        lights = {
            "game": self._game_light(),
            "input": self._input_light(),
            "capture": self._capture_light(),
            "hud": self._hud_light(),
        }
        for key, label in _UNBUILT.items():
            lights[key] = Light(state="off", label=label, detail=_NOT_YET)
        return StatusPayload(lights=lights)
