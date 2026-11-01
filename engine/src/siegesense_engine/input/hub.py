"""Moves events from the input thread onto the asyncio loop in small time-ordered batches."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from collections.abc import Callable

from .events import InputEvent
from .source import InputSource, InputUnavailable

log = logging.getLogger(__name__)
Subscriber = Callable[[list[InputEvent]], None]


class InputHub:
    def __init__(self, source: InputSource, *, flush_interval: float = 0.01) -> None:
        self.source = source
        self._flush_interval = flush_interval
        self._queue: deque[InputEvent] = deque()
        self._subscribers: list[Subscriber] = []
        self._refs = 0
        self._task: asyncio.Task | None = None
        self._start_error: str | None = None

    @property
    def active(self) -> bool:
        return self._refs > 0

    def subscribe(self, cb: Subscriber) -> Callable[[], None]:
        self._subscribers.append(cb)

        def unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._subscribers.remove(cb)

        return unsubscribe

    @property
    def error(self) -> str | None:
        """Why input isn't working: a failed start, or the source reporting it died."""
        return getattr(self.source, "error", None) or self._start_error

    async def acquire(self) -> None:
        if self._refs == 0:
            self._queue.clear()
            try:
                self.source.start(self._queue.append)  # deque.append is thread-safe
            except InputUnavailable as exc:
                self._start_error = str(exc)
                raise
            self._start_error = None
            self._task = asyncio.create_task(self._drain_loop())
        self._refs += 1

    def release(self) -> None:
        if self._refs == 0:
            return
        self._refs -= 1
        if self._refs == 0:
            self.source.stop()
            if self._task:
                self._task.cancel()
                self._task = None
            self._queue.clear()

    async def _drain_loop(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            self.flush()

    def flush(self) -> None:
        if not self._queue:
            return
        batch: list[InputEvent] = []
        while self._queue:
            batch.append(self._queue.popleft())
        batch.sort(key=lambda e: e.t)
        for cb in list(self._subscribers):
            try:
                cb(batch)
            except Exception:
                log.exception("input subscriber failed")
