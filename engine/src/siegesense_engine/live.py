"""Live Mode: screen capture → HUD reading → match timeline → death clips, pushed to the app.
Only the player's own events and round results are shown; nothing about enemies (spec §2)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import cv2
from pydantic import BaseModel, ValidationError

from .capture.frames import CaptureUnavailable, Frame
from .capture.service import CaptureHub
from .clips import ClipWriter
from .errors import RequestError
from .hud.ocr import OcrEngine
from .hud.reader import HudCheckResult, HudReader, HudReading
from .hud.regions import HudRegions
from .input.events import InputEvent, MouseMove
from .input.hub import InputHub
from .input.source import InputUnavailable
from .mechanics.sensitivity import conversion
from .rounds import LiveEvent, RoundSummary, RoundTracker
from .store import Store

log = logging.getLogger(__name__)
Push = Callable[[str, BaseModel | dict], Awaitable[None]]
CLIP_BEFORE, CLIP_AFTER = 10.0, 2.0
HUD_LOW_FOR = 3.0  # s of low-confidence readings before the HUD light turns amber


class LiveEventOut(LiveEvent):
    clip: str | None = None


class DeathInfo(BaseModel):
    round: int
    killer: str | None
    time_alive_s: float | None
    confidence: Literal["ok", "low"]
    clip: str | None


class MatchSummary(BaseModel):
    id: int | None
    started_at: str
    ended_at: str
    rounds: list[RoundSummary]
    deaths: list[DeathInfo]


class LiveService:
    def __init__(
        self,
        capture: CaptureHub,
        input_hub: InputHub,
        store: Store,
        push: Push,
        ocr_factory: Callable[[], OcrEngine],
        clips_dir: Path,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._capture = capture
        self._input = input_hub
        self._store = store
        self._push = push
        self._ocr_factory = ocr_factory
        self._clips = ClipWriter(clips_dir)
        self.clips_dir = clips_dir
        self._clock = clock
        self._running = False
        self._unsubs: list[Callable[[], None]] = []
        self._tasks: set[asyncio.Task] = set()
        self._input_held = False
        self._tracker: RoundTracker | None = None
        self._reader: HudReader | None = None
        self._events: list[LiveEventOut] = []
        self._started_at = datetime.now(UTC)
        self._yaw = 0.0
        self._yaw_scale = 0.0
        self._trace: deque[tuple[float, float]] = deque()
        self._low_since: float | None = None
        self.hud_low = False

    @property
    def running(self) -> bool:
        return self._running

    # -- start / stop --------------------------------------------------------------------
    async def start(self, _: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._running:
            raise RequestError("already_running", "Live Mode is already running.")
        profile = await asyncio.to_thread(self._store.get_profile)
        if profile is None:
            raise RequestError("no_profile", "Finish setup first.")
        try:
            self._capture.acquire(profile.capture_fps)
        except CaptureUnavailable as exc:
            raise RequestError("capture_unavailable", str(exc)) from exc
        loop = asyncio.get_running_loop()
        ocr = await asyncio.to_thread(self._ocr_factory)
        self._reader = HudReader(
            ocr, profile.hud_regions, profile.in_game_name, profile.my_score_side
        )
        self._tracker = RoundTracker(profile.in_game_name)
        self._events = []
        self._started_at = datetime.now(UTC)
        self._yaw, self._yaw_scale = 0.0, conversion(profile).yaw
        self._trace.clear()
        self._low_since, self.hud_low = None, False
        reader = self._reader

        def on_frame(frame: Frame) -> None:  # capture thread
            try:
                reading = reader.read(frame)
            except Exception:
                log.exception("hud read failed")
                return
            loop.call_soon_threadsafe(self._on_reading, reading)

        self._unsubs = [self._capture.subscribe(on_frame)]
        try:
            await self._input.acquire()
            self._input_held = True
            self._unsubs.append(self._input.subscribe(self._on_input))
        except InputUnavailable:
            self._input_held = False  # re-peeks need input; the rest works without it
        self._running = True
        return {"started_at": self._started_at.isoformat()}

    async def stop(self, _: dict[str, Any] | None = None) -> MatchSummary:
        if not self._running:
            raise RequestError("not_running", "Live Mode is not running.")
        self._running = False
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=CLIP_AFTER + 8)
        self._capture.release()
        if self._input_held:
            self._input.release()
            self._input_held = False
        tracker = self._tracker
        rounds = tracker.rounds() if tracker else []
        deaths = [
            DeathInfo(
                round=e.round,
                killer=e.data.get("killer"),
                time_alive_s=e.data.get("time_alive_s"),
                confidence=e.confidence,
                clip=e.clip,
            )
            for e in self._events
            if e.kind == "death"
        ]
        summary = MatchSummary(
            id=None,
            started_at=self._started_at.isoformat(),
            ended_at=datetime.now(UTC).isoformat(),
            rounds=rounds,
            deaths=deaths,
        )
        summary.id = await asyncio.to_thread(
            self._store.add_match,
            summary.started_at,
            summary.ended_at,
            summary.model_dump(mode="json"),
            [e.model_dump(mode="json") for e in self._events],
        )
        return summary

    async def shutdown(self) -> None:
        if self._running:
            with contextlib.suppress(Exception):
                await self.stop()

    # -- input (asyncio thread) --------------------------------------------------------
    def _on_input(self, events: list[InputEvent]) -> None:
        tracker = self._tracker
        for e in events:
            if isinstance(e, MouseMove) and e.dx:
                self._yaw += e.dx * self._yaw_scale
                self._trace.append((e.t, round(self._yaw, 3)))
                if tracker:
                    tracker.input(e.t, self._yaw)
        while self._trace and self._trace[-1][0] - self._trace[0][0] > CLIP_BEFORE + CLIP_AFTER + 5:
            self._trace.popleft()

    # -- readings (asyncio thread) -----------------------------------------------------
    def _on_reading(self, reading: HudReading) -> None:
        if not self._running or self._tracker is None:
            return
        if reading.confidence == "low":
            self._low_since = self._low_since or reading.t
            self.hud_low = reading.t - self._low_since >= HUD_LOW_FOR
        else:
            self._low_since, self.hud_low = None, False
        for event in self._tracker.hud(reading):
            out = LiveEventOut(**event.model_dump())
            if out.kind == "death":
                self._spawn(self._clip_then_push(out))
            else:
                self._events.append(out)
                self._spawn(self._push("live_event", out))
            if out.kind == "round_end":
                summary = next((r for r in self._tracker.rounds() if r.number == out.round), None)
                if summary is not None:
                    self._spawn(self._push("round_summary", summary))

    def _spawn(self, coro) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _clip_then_push(self, event: LiveEventOut) -> None:
        wait = event.t + CLIP_AFTER + 0.2 - self._clock()
        if wait > 0:
            await asyncio.sleep(wait)
        frames = self._capture.ring.window(event.t - CLIP_BEFORE, event.t + CLIP_AFTER)
        trace = [
            {"t": round(t - event.t, 3), "yaw": y}
            for t, y in self._trace
            if event.t - CLIP_BEFORE <= t <= event.t + CLIP_AFTER
        ]
        name = f"{self._started_at:%Y%m%d-%H%M%S}-r{event.round}-death"
        path = await asyncio.to_thread(self._clips.write, frames, trace, name)
        event.clip = path.name if path else None
        self._events.append(event)
        await self._push("live_event", event)

    # -- HUD check ---------------------------------------------------------------------
    async def _reader_for_check(self, payload: dict[str, Any] | None) -> HudReader:
        """Uses the saved profile, or the unsaved boxes/side the player is editing."""
        payload = payload or {}
        profile = await asyncio.to_thread(self._store.get_profile)
        name = payload.get("in_game_name") or (profile.in_game_name if profile else None)
        if not name:
            raise RequestError("no_profile", "Finish setup first.")
        regions = profile.hud_regions if profile else HudRegions()
        if payload.get("regions") is not None:
            try:
                regions = HudRegions.model_validate(payload["regions"])
            except ValidationError as exc:
                raise RequestError("invalid_regions", str(exc.errors()[0]["msg"])) from exc
        side = payload.get("my_score_side") or (profile.my_score_side if profile else "left")
        ocr = await asyncio.to_thread(self._ocr_factory)
        return HudReader(ocr, regions, name, side if side in ("left", "right") else "left")

    async def hud_check(self, payload: dict[str, Any] | None = None) -> HudCheckResult:
        reader = await self._reader_for_check(payload)
        got: asyncio.Future[Frame] = asyncio.get_running_loop().create_future()
        loop = asyncio.get_running_loop()

        def on_frame(frame: Frame) -> None:
            loop.call_soon_threadsafe(lambda: got.done() or got.set_result(frame))

        try:
            self._capture.acquire(30)
        except CaptureUnavailable as exc:
            raise RequestError("capture_unavailable", str(exc)) from exc
        unsub = self._capture.subscribe(on_frame, every_frame=True)
        try:
            frame = await asyncio.wait_for(got, timeout=3)
        except TimeoutError as exc:
            raise RequestError(
                "no_frame", "No screen frame arrived. Is a game window open?"
            ) from exc
        finally:
            unsub()
            self._capture.release()
        return await asyncio.to_thread(reader.snapshot, frame)

    async def hud_check_file(self, payload: dict[str, Any]) -> HudCheckResult:
        path = Path(str(payload.get("path", "")))
        image = await asyncio.to_thread(cv2.imread, str(path)) if path.is_file() else None
        if image is None:
            raise RequestError("not_found", f"Could not open image: {path}")
        reader = await self._reader_for_check(payload)
        return await asyncio.to_thread(reader.snapshot, Frame(self._clock(), image))

    async def clip_dir(self, _: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"dir": str(self.clips_dir)}
