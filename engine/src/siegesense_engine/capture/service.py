"""Screen capture (spec §4.3, §7 performance guard).

Two threads:
- the capture thread keeps the ring buffer (death clips) filled at full frame rate and feeds
  cheap per-frame consumers;
- the HUD worker reads the HUD from the latest frame at a lower rate, so slow OCR never makes
  clips choppy.

When the HUD work can't keep up, the guard first lowers the HUD rate, then the capture frame
rate (without restarting sources that can't change rate, like a replay video).
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from .frames import CaptureUnavailable, Frame, FrameSource
from .ring import FrameRing

log = logging.getLogger(__name__)
Subscriber = Callable[[Frame], None]

# Guard levels: 0 = full quality; first lower the HUD rate, then the capture frame rate.
LEVELS: tuple[tuple[int, float], ...] = ((30, 10.0), (30, 6.0), (30, 4.0), (24, 4.0), (20, 4.0))


@dataclass(frozen=True)
class CaptureStats:
    fps_target: int
    fps_actual: float
    hud_hz: float
    behind: bool


class CaptureService:
    def __init__(
        self,
        source: FrameSource,
        ring: FrameRing,
        hud_hz: float = 10.0,
        guard_window: float = 3.0,
        recover_after: float = 30.0,
    ) -> None:
        self.source = source
        self.ring = ring
        self._base_hud = hud_hz
        self._guard_window = guard_window
        self._recover_after = recover_after
        self._subscribers: list[Subscriber] = []
        self._every_frame: list[Subscriber] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._hud_slot: Frame | None = None
        self._hud_ready = threading.Event()
        self.error: str | None = None
        self._reset(30)

    def _reset(self, fps: int) -> None:
        self._base_fps = fps
        self._level = 0
        self._fps = fps
        self._hud_hz = self._base_hud
        self._work: deque[tuple[float, float]] = deque()
        self._frames: deque[float] = deque()
        self._fast_since: float | None = None
        self.error = None

    # -- subscribers -------------------------------------------------------------------
    def subscribe(self, cb: Subscriber, every_frame: bool = False) -> Callable[[], None]:
        """HUD consumers get frames at the HUD rate on the HUD worker; cheap ``every_frame``
        consumers get every frame on the capture thread."""
        target = self._every_frame if every_frame else self._subscribers
        with self._lock:
            target.append(cb)

        def unsubscribe() -> None:
            with self._lock, contextlib.suppress(ValueError):
                target.remove(cb)

        return unsubscribe

    # -- lifecycle ---------------------------------------------------------------------
    def start(self, fps: int) -> None:
        self._reset(fps)
        self.source.start(fps)
        self.source.latest()  # drop anything captured before this start
        self._stop.clear()
        self._hud_slot = None
        self._threads = [
            threading.Thread(target=self._capture_loop, daemon=True, name="capture"),
            threading.Thread(target=self._hud_loop, daemon=True, name="hud"),
        ]
        for t in self._threads:
            t.start()

    def stop(self) -> None:
        self._stop.set()
        self._hud_ready.set()
        for t in self._threads:
            t.join(timeout=2)
        self._threads = []
        self.source.stop()

    def stats(self) -> CaptureStats:
        now = time.perf_counter()
        with self._lock:
            recent = sum(1 for t in self._frames if now - t <= 1.0)
        return CaptureStats(self._fps, float(recent), self._hud_hz, self._level > 0)

    # -- capture thread ----------------------------------------------------------------
    def _capture_loop(self) -> None:
        last_hud = 0.0
        while not self._stop.is_set():
            frame = self.source.latest()
            if frame is None:
                time.sleep(0.002)
                continue
            with self._lock:
                self._frames.append(frame.t)
                while self._frames and frame.t - self._frames[0] > 2.0:
                    self._frames.popleft()
            try:
                self.ring.add(frame)
            except Exception:
                log.exception("ring buffer add failed")
            self._dispatch(frame, self._every_frame)
            if frame.t - last_hud >= 1.0 / self._hud_hz:
                last_hud = frame.t
                self._hud_slot = frame  # the HUD worker always takes the newest frame
                self._hud_ready.set()

    # -- HUD worker --------------------------------------------------------------------
    def _hud_loop(self) -> None:
        last_guard = time.perf_counter()
        while not self._stop.is_set():
            self._hud_ready.wait(timeout=0.25)
            self._hud_ready.clear()
            frame, self._hud_slot = self._hud_slot, None
            if frame is not None and not self._stop.is_set():
                start = time.perf_counter()
                self._dispatch(frame, self._subscribers)
                end = time.perf_counter()
                self._work.append((end, end - start))  # stamped when the work finished
            now = time.perf_counter()
            if now - last_guard >= min(1.0, self._guard_window / 3):
                last_guard = now
                self._guard(now)

    def _dispatch(self, frame: Frame, targets: list[Subscriber]) -> None:
        with self._lock:
            subscribers = list(targets)
        for cb in subscribers:
            try:
                cb(frame)
            except Exception:
                log.exception("capture subscriber failed")

    # -- performance guard -------------------------------------------------------------
    def _guard(self, now: float) -> None:
        while self._work and now - self._work[0][0] > self._guard_window:
            self._work.popleft()
        if not self._work:
            return
        budget = 1.0 / self._hud_hz
        avg = sum(d for _, d in self._work) / len(self._work)
        if avg > budget and self._level < len(LEVELS) - 1:
            self._set_level(self._level + 1)
            self._work.clear()
            self._fast_since = None
        elif self._level > 0 and avg < 0.5 * budget:
            self._fast_since = self._fast_since or now
            if now - self._fast_since >= self._recover_after:
                self._set_level(self._level - 1)
                self._fast_since = None
        else:
            self._fast_since = None

    def _set_level(self, level: int) -> None:
        self._level = level
        fps, hud = LEVELS[level]
        self._hud_hz = min(self._base_hud, hud)
        fps = min(self._base_fps, fps)
        if fps != self._fps:
            self._fps = fps
            set_fps = getattr(self.source, "set_fps", None)
            if set_fps is not None:
                try:
                    set_fps(fps)
                except Exception as exc:
                    self.error = f"Screen capture stopped: {exc}"
                    log.exception("could not change capture rate")
        log.info("capture level %s: %s fps, HUD %.0f Hz", level, self._fps, self._hud_hz)


class CaptureHub:
    """Shares one capture between Live Mode and Warm-up (reference counted, like InputHub)."""

    def __init__(self, source: FrameSource, ring: FrameRing | None = None) -> None:
        self.source = source
        self.service = CaptureService(source, ring or FrameRing())
        self._refs = 0
        self._start_error: str | None = None

    @property
    def error(self) -> str | None:
        return self._start_error or (self.service.error if self._refs else None)

    @property
    def active(self) -> bool:
        return self._refs > 0

    @property
    def ring(self) -> FrameRing:
        return self.service.ring

    def subscribe(self, cb: Subscriber, every_frame: bool = False) -> Callable[[], None]:
        return self.service.subscribe(cb, every_frame)

    def acquire(self, fps: int = 30) -> None:
        if self._refs == 0:
            try:
                self.service.start(fps)
            except CaptureUnavailable as exc:
                self._start_error = str(exc)
                raise
            self._start_error = None
        self._refs += 1

    def release(self) -> None:
        if self._refs == 0:
            return
        self._refs -= 1
        if self._refs == 0:
            self.service.stop()
            self.service.ring.clear()
