"""The capture thread: keeps the ring buffer filled, hands frames to HUD/warm-up consumers at a
lower rate, and backs off when the PC can't keep up (spec §4.3, §7 performance guard)."""

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

FPS_STEPS = (30, 24, 20)
HUD_STEPS = (10.0, 6.0, 4.0)


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
        self._hud_hz = hud_hz
        self._guard_window = guard_window
        self._recover_after = recover_after
        self._subscribers: list[Subscriber] = []
        self._every_frame: list[Subscriber] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._base_fps = 30
        self._fps = 30
        self._level = 0  # 0 = full quality; each step lowers fps, then HUD rate
        self._work: deque[tuple[float, float]] = deque()  # (t, seconds of consumer work)
        self._frames: deque[float] = deque()
        self._fast_since: float | None = None
        self._restart_fps: int | None = None

    # -- subscribers -------------------------------------------------------------------
    def subscribe(self, cb: Subscriber, every_frame: bool = False) -> Callable[[], None]:
        """HUD consumers get frames at the HUD rate; cheap ``every_frame`` consumers get all."""
        target = self._every_frame if every_frame else self._subscribers
        with self._lock:
            target.append(cb)

        def unsubscribe() -> None:
            with self._lock, contextlib.suppress(ValueError):
                target.remove(cb)

        return unsubscribe

    # -- lifecycle ---------------------------------------------------------------------
    def start(self, fps: int) -> None:
        self._base_fps = self._fps = fps
        self._level = 0
        self._hud_hz = self._base_hud
        self.source.start(fps)
        self.source.latest()  # drop anything captured before this start
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="capture")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self.source.stop()

    def stats(self) -> CaptureStats:
        now = time.perf_counter()
        recent = [t for t in self._frames if now - t <= 1.0]
        return CaptureStats(self._fps, float(len(recent)), self._hud_hz, self._level > 0)

    # -- loop --------------------------------------------------------------------------
    def _run(self) -> None:
        last_hud = 0.0
        last_guard = time.perf_counter()
        while not self._stop.is_set():
            if self._restart_fps is not None:
                fps, self._restart_fps = self._restart_fps, None
                with contextlib.suppress(Exception):
                    self.source.stop()
                    self.source.start(fps)
            frame = self.source.latest()
            if frame is None:
                time.sleep(0.002)
            else:
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
                    start = time.perf_counter()
                    self._dispatch(frame, self._subscribers)
                    self._work.append((start, time.perf_counter() - start))
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

    def _guard(self, now: float) -> None:
        while self._work and now - self._work[0][0] > self._guard_window:
            self._work.popleft()
        if not self._work:
            return
        budget = 1.0 / self._hud_hz
        avg = sum(d for _, d in self._work) / len(self._work)
        if avg > budget and self._level < len(FPS_STEPS) + len(HUD_STEPS) - 2:
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
        fps_idx = min(level, len(FPS_STEPS) - 1)
        hud_idx = max(0, level - (len(FPS_STEPS) - 1))
        fps = min(self._base_fps, FPS_STEPS[fps_idx]) if level else self._base_fps
        self._hud_hz = min(self._base_hud, HUD_STEPS[hud_idx])
        if fps != self._fps:
            self._fps = fps
            self._restart_fps = fps
        log.info("capture level %s: %s fps, HUD %.0f Hz", level, self._fps, self._hud_hz)


class CaptureHub:
    """Shares one capture between Live Mode and Warm-up (reference counted, like InputHub)."""

    def __init__(self, source: FrameSource, ring: FrameRing | None = None) -> None:
        self.source = source
        self.service = CaptureService(source, ring or FrameRing())
        self._refs = 0
        self.error: str | None = None

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
                self.error = str(exc)
                raise
            self.error = None
        self._refs += 1

    def release(self) -> None:
        if self._refs == 0:
            return
        self._refs -= 1
        if self._refs == 0:
            self.service.stop()
            self.service.ring.clear()
