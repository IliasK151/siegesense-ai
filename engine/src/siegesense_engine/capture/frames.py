"""Where screen frames come from: DXGI desktop duplication on Windows, a video file for replay,
or a fake for tests. Capture only reads what is on screen; the game is never touched."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass
class Frame:
    t: float  # time.perf_counter() seconds
    image: np.ndarray  # BGR, full resolution


class CaptureUnavailable(RuntimeError):
    pass


class FrameSource(Protocol):
    available: bool
    reason: str | None
    size: tuple[int, int]

    def start(self, fps: int) -> None: ...

    def latest(self) -> Frame | None: ...

    def stop(self) -> None: ...


class FakeFrameSource:
    available = True
    reason = None

    def __init__(self, size: tuple[int, int] = (1920, 1080)) -> None:
        self.size = size
        self.started = False
        self._latest: Frame | None = None
        self._lock = threading.Lock()

    def start(self, fps: int) -> None:
        self.started = True

    def push(self, image: np.ndarray, t: float | None = None) -> None:
        with self._lock:
            self._latest = Frame(time.perf_counter() if t is None else t, image)

    def latest(self) -> Frame | None:
        with self._lock:
            frame, self._latest = self._latest, None
        return frame

    def stop(self) -> None:
        self.started = False


class UnavailableFrameSource:
    available = False
    size = (0, 0)

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def start(self, fps: int) -> None:
        raise CaptureUnavailable(self.reason)

    def latest(self) -> Frame | None:
        return None

    def stop(self) -> None:
        pass


class VideoFileSource:
    """Decodes a video file as if it were the screen (replay mode)."""

    available = True
    reason = None

    def __init__(self, path: Path, realtime: bool = True, loop: bool = False) -> None:
        import av

        self._path = Path(path)
        self._realtime = realtime
        self._loop = loop
        with av.open(str(self._path)) as c:
            s = c.streams.video[0]
            self.size = (s.codec_context.width, s.codec_context.height)
        self._latest: Frame | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.finished = False

    def start(self, fps: int) -> None:
        self._stop.clear()
        self.finished = False
        with self._lock:
            self._latest = None  # never hand out a frame from a previous run
        self._thread = threading.Thread(target=self._run, daemon=True, name="video-source")
        self._thread.start()

    def _run(self) -> None:
        import av

        try:
            while not self._stop.is_set():
                with av.open(str(self._path)) as container:
                    stream = container.streams.video[0]
                    t_start = time.perf_counter()
                    first: float | None = None
                    for frame in container.decode(stream):
                        if self._stop.is_set():
                            return
                        pts = float(frame.time or 0.0)
                        first = pts if first is None else first
                        if self._realtime:
                            delay = t_start + (pts - first) - time.perf_counter()
                            if delay > 0 and self._stop.wait(delay):
                                return
                        else:
                            # Hand frames over one at a time.
                            while not self._stop.is_set():
                                with self._lock:
                                    if self._latest is None:
                                        break
                                time.sleep(0.001)
                        image = frame.to_ndarray(format="bgr24")
                        with self._lock:
                            self._latest = Frame(time.perf_counter(), image)
                if not self._loop:
                    break
        finally:
            self.finished = True

    def latest(self) -> Frame | None:
        with self._lock:
            frame, self._latest = self._latest, None
        return frame

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            self._latest = None


class DxcamSource:
    """Windows desktop duplication (works with Siege in borderless or windowed mode)."""

    reason: str | None = None

    def __init__(self, output_idx: int = 0) -> None:
        self.available = sys.platform == "win32"
        self.size = (0, 0)
        self._output_idx = output_idx
        self._camera = None
        if not self.available:
            self.reason = "Screen capture works on Windows only"

    def start(self, fps: int) -> None:
        if not self.available:
            raise CaptureUnavailable(self.reason or "unavailable")
        try:
            import dxcam

            if self._camera is None:
                self._camera = dxcam.create(output_idx=self._output_idx, output_color="BGR")
            self.size = (self._camera.width, self._camera.height)
            self._camera.start(target_fps=fps, video_mode=True)
        except Exception as exc:  # driver/DXGI problems surface here
            self._camera = None
            raise CaptureUnavailable(f"Could not start screen capture: {exc}") from exc

    def latest(self) -> Frame | None:
        if self._camera is None:
            return None
        image = self._camera.get_latest_frame()
        return None if image is None else Frame(time.perf_counter(), image)

    def stop(self) -> None:
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                pass


def default_frame_source() -> FrameSource:
    if sys.platform == "win32":
        return DxcamSource()
    return UnavailableFrameSource("Screen capture works on Windows only")
