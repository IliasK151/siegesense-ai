"""Detects whether Rainbow Six Siege is running and focused.

Only looks at the process list and the foreground window. Never opens the game process.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol

import psutil

GAME_PROCESS_NAMES = ("RainbowSix.exe", "RainbowSix_BE.exe", "RainbowSix_Vulkan.exe")
_NAMES_LOWER = {n.lower() for n in GAME_PROCESS_NAMES}


@dataclass
class GameState:
    running: bool = False
    focused: bool = False


class GameWatcher(Protocol):
    def poll(self) -> GameState: ...


class FakeGameWatcher:
    def __init__(self, state: GameState | None = None) -> None:
        self.state = state or GameState()

    def poll(self) -> GameState:
        return self.state


class PsutilGameWatcher:
    def poll(self) -> GameState:
        pids = [
            p.info.get("pid")
            for p in psutil.process_iter(["name", "pid"])
            if (p.info.get("name") or "").lower() in _NAMES_LOWER
        ]
        if not pids:
            return GameState(False, False)
        return GameState(True, _foreground_pid() in pids)


def _foreground_pid() -> int | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def default_game_watcher() -> GameWatcher:
    return PsutilGameWatcher()
