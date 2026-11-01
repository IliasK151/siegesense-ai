import threading
import time

import numpy as np
import pytest

from siegesense_engine.capture.frames import (
    CaptureUnavailable,
    FakeFrameSource,
    UnavailableFrameSource,
)
from siegesense_engine.capture.ring import FrameRing
from siegesense_engine.capture.service import CaptureHub, CaptureService

IMG = np.zeros((90, 160, 3), np.uint8)


class Pusher:
    """Feeds a FakeFrameSource at a steady rate from another thread."""

    def __init__(self, source, hz=60):
        self.source, self.hz = source, hz
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            self.source.push(IMG.copy())
            time.sleep(1 / self.hz)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        self._t.join()


def wait(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > end:
            raise TimeoutError
        time.sleep(0.01)


def test_ring_filled():
    src, ring = FakeFrameSource(), FrameRing(width=160)
    svc = CaptureService(src, ring)
    with Pusher(src):
        svc.start(30)
        wait(lambda: ring.memory_bytes() > 0 and len(ring.window(0, 1e12)) >= 10)
        svc.stop()


def test_hud_rate():
    src, ring = FakeFrameSource(), FrameRing(width=160)
    calls = []
    svc = CaptureService(src, ring, hud_hz=10)
    svc.subscribe(lambda f: calls.append(f.t))
    with Pusher(src):
        svc.start(30)
        time.sleep(1.0)
        svc.stop()
    assert 7 <= len(calls) <= 12


def test_performance_guard_steps_down():
    src, ring = FakeFrameSource(), FrameRing(width=160)
    svc = CaptureService(src, ring, hud_hz=10, guard_window=0.5)
    svc.subscribe(lambda f: time.sleep(0.15))  # 150 ms of work vs a 100 ms budget
    with Pusher(src):
        svc.start(30)
        wait(lambda: svc.stats().behind, timeout=4)
        stats = svc.stats()
        svc.stop()
    assert stats.fps_target < 30 or stats.hud_hz < 10


def test_recovers_when_fast():
    src, ring = FakeFrameSource(), FrameRing(width=160)
    slow = {"on": True}
    svc = CaptureService(src, ring, hud_hz=10, guard_window=0.3, recover_after=0.6)
    svc.subscribe(lambda f: time.sleep(0.15 if slow["on"] else 0.0))
    with Pusher(src):
        svc.start(30)
        wait(lambda: svc.stats().behind, timeout=4)
        slow["on"] = False
        wait(lambda: not svc.stats().behind, timeout=6)
        svc.stop()
    assert svc.stats().fps_target == 30 and svc.stats().hud_hz == 10


def test_subscriber_error_does_not_stop_capture():
    src, ring = FakeFrameSource(), FrameRing(width=160)
    good = []
    svc = CaptureService(src, ring, hud_hz=20)
    svc.subscribe(lambda f: 1 / 0)
    svc.subscribe(lambda f: good.append(1))
    with Pusher(src):
        svc.start(30)
        wait(lambda: len(good) >= 3)
        svc.stop()


def test_hub_refcount():
    src = FakeFrameSource()
    hub = CaptureHub(src)
    hub.acquire(30)
    hub.acquire(30)
    assert src.started and hub.active
    hub.release()
    assert src.started
    hub.release()
    assert not src.started and not hub.active


def test_hub_unavailable():
    hub = CaptureHub(UnavailableFrameSource("Screen capture works on Windows only"))
    with pytest.raises(CaptureUnavailable, match="Windows only"):
        hub.acquire(30)
    assert not hub.active and hub.error == "Screen capture works on Windows only"
