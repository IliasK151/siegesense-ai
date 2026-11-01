"""Input events from the player's own mouse and keyboard.

``t`` is seconds from ``time.perf_counter()``. ``dy > 0`` means the mouse moved down
(Windows convention).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Literal

ButtonName = Literal["left", "right", "middle", "x1", "x2"]


@dataclass(frozen=True, slots=True)
class MouseMove:
    t: float
    dx: int
    dy: int


@dataclass(frozen=True, slots=True)
class Button:
    t: float
    button: ButtonName
    down: bool


@dataclass(frozen=True, slots=True)
class Key:
    t: float
    vk: int
    down: bool


InputEvent = MouseMove | Button | Key

# Windows virtual-key codes for the default Siege binds we care about.
VK = SimpleNamespace(W=0x57, A=0x41, S=0x53, D=0x44, C=0x43, F8=0x77)
