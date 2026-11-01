"""Where input comes from: real Windows Raw Input, a replay file, or a test fake."""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .events import Button, InputEvent, Key, MouseMove

Sink = Callable[[InputEvent], None]


class InputUnavailable(RuntimeError):
    """Input tracking can't run here (not Windows, or Windows refused registration)."""


class InputSource(Protocol):
    available: bool
    reason: str | None

    def start(self, sink: Sink) -> None: ...

    def stop(self) -> None: ...


class FakeInputSource:
    available = True
    reason = None
    error: str | None = None

    def __init__(self) -> None:
        self.started = False
        self._sink: Sink | None = None

    def start(self, sink: Sink) -> None:
        self._sink = sink
        self.started = True

    def stop(self) -> None:
        self.started = False
        self._sink = None

    def emit(self, *events: InputEvent) -> None:
        sink = self._sink
        if sink is not None:
            for e in events:
                sink(e)


class UnavailableInputSource:
    available = False

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def start(self, sink: Sink) -> None:
        raise InputUnavailable(self.reason)

    def stop(self) -> None:
        pass


def _decode_line(raw: dict) -> InputEvent:
    t = float(raw["t"])
    kind = raw["k"]
    if kind == "m":
        return MouseMove(t, int(raw["dx"]), int(raw["dy"]))
    if kind == "b":
        return Button(t, raw["b"], bool(raw["d"]))
    if kind == "k":
        return Key(t, int(raw["vk"]), bool(raw["d"]))
    raise ValueError(f"unknown replay event kind: {kind}")


class ReplayInputSource:
    """Plays a recorded JSONL input file with its original timing (re-based to now)."""

    available = True
    reason = None

    def __init__(self, path: Path, speed: float = 1.0) -> None:
        self._events = [
            _decode_line(json.loads(line))
            for line in Path(path).read_text().splitlines()
            if line.strip()
        ]
        self._speed = speed
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, sink: Sink) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(sink,), daemon=True)
        self._thread.start()

    def _run(self, sink: Sink) -> None:
        if not self._events:
            return
        t_first = self._events[0].t
        t_start = time.perf_counter()
        for e in self._events:
            target = t_start + (e.t - t_first) / self._speed
            delay = target - time.perf_counter()
            if delay > 0 and self._stop.wait(delay):
                return
            if self._stop.is_set():
                return
            sink(_retime(e, target))

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)


def _retime(e: InputEvent, t: float) -> InputEvent:
    if isinstance(e, MouseMove):
        return MouseMove(t, e.dx, e.dy)
    if isinstance(e, Button):
        return Button(t, e.button, e.down)
    return Key(t, e.vk, e.down)


def default_input_source() -> InputSource:
    if sys.platform == "win32":
        from .rawinput import RawInputSource

        return RawInputSource()
    return UnavailableInputSource("Input tracking works on Windows only")
