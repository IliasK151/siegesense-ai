"""Warm-up and calibration features, wired to the input hub, the store and app pushes."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import cv2
from pydantic import BaseModel

from .calibration import CalibrationSession, CalibrationState
from .capture.frames import CaptureUnavailable
from .capture.service import CaptureHub
from .errors import RequestError
from .hud.regions import crop
from .input.events import InputEvent
from .input.hub import InputHub
from .input.source import InputUnavailable
from .mechanics.sensitivity import conversion
from .store import Store
from .warmup import HistoryPoint, WarmupSession, WarmupSummary, summarize

log = logging.getLogger(__name__)
Push = Callable[[str, BaseModel | dict], Awaitable[None]]
FLUSH_AHEAD = 1.0  # s; on stop, resolve flicks still waiting for their shot window


async def _acquire(hub: InputHub) -> None:
    try:
        await hub.acquire()
    except InputUnavailable as exc:
        raise RequestError("input_unavailable", str(exc)) from exc


class WarmupService:
    def __init__(
        self,
        hub: InputHub,
        store: Store,
        push: Push,
        clock: Callable[[], float] = time.perf_counter,
        metrics_interval: float = 0.5,
        capture: CaptureHub | None = None,
    ) -> None:
        self._hub = hub
        self.is_busy: Callable[[], bool] = lambda: False
        self._capture = capture
        self._capture_unsub: Callable[[], None] | None = None
        self._store = store
        self._push = push
        self._clock = clock
        self._interval = metrics_interval
        self._session: WarmupSession | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._ticker: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._session is not None

    async def start(self, _: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._session is not None:
            raise RequestError("already_running", "A warm-up is already running.")
        if self.is_busy():
            raise RequestError("busy", "Stop Live Mode first.")
        profile = await asyncio.to_thread(self._store.get_profile)
        if profile is None:
            raise RequestError("no_profile", "Finish setup first.")
        await _acquire(self._hub)
        conv = conversion(profile)
        self._session = WarmupSession(conv, datetime.now(UTC), t0=self._clock())
        self._unsubscribe = self._hub.subscribe(self._on_batch)
        self._start_capture(profile)
        self._ticker = asyncio.create_task(self._tick_loop())
        return {"conversion": conv.source}

    def _start_capture(self, profile) -> None:
        """Reaction time needs the screen; warm-up works without it."""
        if self._capture is None:
            return
        try:
            self._capture.acquire(profile.capture_fps)
        except CaptureUnavailable:
            return
        box = profile.hud_regions.centre
        session = self._session

        def on_frame(frame) -> None:
            centre = cv2.cvtColor(crop(frame.image, box), cv2.COLOR_BGR2GRAY)
            if session is not None:
                session.frame(frame.t, cv2.resize(centre, (64, 64), interpolation=cv2.INTER_AREA))

        self._capture_unsub = self._capture.subscribe(on_frame, every_frame=True)

    def _stop_capture(self) -> None:
        if self._capture_unsub is not None:
            self._capture_unsub()
            self._capture_unsub = None
            if self._capture is not None:
                self._capture.release()

    def _on_batch(self, events: list[InputEvent]) -> None:
        if self._session is not None:
            self._session.feed(events)

    async def _publish(self, now: float) -> None:
        session = self._session
        if session is None:
            return
        for f in session.poll(now):
            await self._push("flick", f)
        await self._push("metrics", session.metrics(now))

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self._publish(self._clock())
            except Exception:
                log.exception("warm-up tick failed")

    async def stop(self, _: dict[str, Any] | None = None) -> WarmupSummary:
        session = self._session
        if session is None:
            raise RequestError("not_running", "No warm-up is running.")
        if self._ticker:
            self._ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ticker
        self._hub.flush()
        end = self._clock()
        for f in session.poll(end + FLUSH_AHEAD):
            await self._push("flick", f)
        metrics = session.metrics(end)
        self._session = None
        if self._unsubscribe:
            self._unsubscribe()
        self._hub.release()
        self._stop_capture()

        history = await asyncio.to_thread(self._store.recent_warmups, 7)
        summary = summarize(metrics, session.started_at, end - session.t0, history)
        summary.id = await asyncio.to_thread(self._store.add_warmup, summary)
        summary.history = [
            *history[-6:],
            HistoryPoint(started_at=summary.started_at, score=metrics.score),
        ]
        return summary

    async def history(self, _: dict[str, Any] | None = None) -> dict[str, Any]:
        points = await asyncio.to_thread(self._store.recent_warmups, 7)
        return {"history": [p.model_dump() for p in points]}

    async def shutdown(self) -> None:
        if self._session is not None:
            with contextlib.suppress(Exception):
                await self.stop()


class CalibrationService:
    MIN_PUSH_INTERVAL = 0.05  # s, while the live counter is moving

    def __init__(self, hub: InputHub, push: Push, clock: Callable[[], float] = time.perf_counter):
        self._hub = hub
        self._push = push
        self._clock = clock
        self._session: CalibrationSession | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._last_push = 0.0
        self._last_shape: tuple | None = None

    async def start(self, _: dict[str, Any] | None = None) -> CalibrationState:
        self._end()
        await _acquire(self._hub)
        self._session = CalibrationSession()
        self._unsubscribe = self._hub.subscribe(self._on_batch)
        state = self._session.state()
        self._last_shape = self._shape(state)
        return state

    async def cancel(self, _: dict[str, Any] | None = None) -> CalibrationState:
        session = self._session
        if session is None:
            return CalibrationState(phase="cancelled", runs=[], current_counts=0)
        session.cancel()
        self._end()
        return session.state()

    @staticmethod
    def _shape(s: CalibrationState) -> tuple:
        return (s.phase, tuple(s.runs), s.warning)

    def _start_capture(self, profile) -> None:
        """Reaction time needs the screen; warm-up works without it."""
        if self._capture is None:
            return
        try:
            self._capture.acquire(profile.capture_fps)
        except CaptureUnavailable:
            return
        box = profile.hud_regions.centre
        session = self._session

        def on_frame(frame) -> None:
            centre = cv2.cvtColor(crop(frame.image, box), cv2.COLOR_BGR2GRAY)
            if session is not None:
                session.frame(frame.t, cv2.resize(centre, (64, 64), interpolation=cv2.INTER_AREA))

        self._capture_unsub = self._capture.subscribe(on_frame, every_frame=True)

    def _stop_capture(self) -> None:
        if self._capture_unsub is not None:
            self._capture_unsub()
            self._capture_unsub = None
            if self._capture is not None:
                self._capture.release()

    def _on_batch(self, events: list[InputEvent]) -> None:
        session = self._session
        if session is None or not session.feed(events):
            return
        state = session.state()
        shape = self._shape(state)
        now = self._clock()
        if shape == self._last_shape and now - self._last_push < self.MIN_PUSH_INTERVAL:
            return
        self._last_shape, self._last_push = shape, now
        asyncio.get_running_loop().create_task(self._push("calibration", state))
        if state.phase == "done":
            self._end()

    def _end(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        if self._session is not None:
            self._session = None
            self._hub.release()
