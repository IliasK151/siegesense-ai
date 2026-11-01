import numpy as np
from hudsynth import render

from siegesense_engine.capture.frames import FakeFrameSource, Frame, VideoFileSource
from siegesense_engine.capture.ring import FrameRing
from siegesense_engine.hud.regions import HudRegions, crop


def test_render_draws_regions():
    img = render({"timer": 165, "score": (2, 1), "health": 87,
                  "kills": [("Ash.Main", "blue", "Thermite_1", "orange")]})  # fmt: skip
    assert img.shape == (1080, 1920, 3)
    assert (crop(img, HudRegions().timer) > 150).any()
    assert (crop(img, HudRegions().killfeed) > 150).any()


def _frame(t, size=(640, 360)):
    return Frame(
        t, np.random.default_rng(int(t * 100)).integers(0, 255, (size[1], size[0], 3), np.uint8)
    )


def test_ring_keeps_window():
    ring = FrameRing(seconds=15, fps=30, width=320)
    for i in range(20 * 30):
        ring.add(_frame(i / 30))
    frames = ring.window(0, 100)
    assert frames[0][0] >= 20 - 15 - 0.05
    assert len(frames) <= 15 * 30 + 1


def test_ring_window_slice():
    ring = FrameRing(seconds=15, fps=30, width=320)
    for i in range(300):
        ring.add(_frame(i / 30))
    sl = ring.window(2.0, 3.0)
    assert all(2.0 <= t <= 3.0 for t, _ in sl)
    assert 29 <= len(sl) <= 31
    assert sl[0][1][:2] == b"\xff\xd8"  # JPEG


def test_ring_memory_bounded():
    ring = FrameRing(seconds=15, fps=30)
    img = render({"timer": 100, "score": (1, 1), "health": 100, "kills": []})
    for i in range(15 * 30):
        ring.add(Frame(i / 30, img))
    assert ring.memory_bytes() < 60 * 1024 * 1024


def test_fake_source_latest():
    src = FakeFrameSource(size=(64, 36))
    src.start(30)
    assert src.latest() is None
    src.push(np.zeros((36, 64, 3), np.uint8), 1.0)
    src.push(np.ones((36, 64, 3), np.uint8), 1.1)
    f = src.latest()
    assert f.t == 1.1 and f.image.max() == 1
    assert src.latest() is None


def test_video_file_source(tmp_path):
    import av

    path = tmp_path / "v.mp4"
    out = av.open(str(path), "w")
    stream = out.add_stream("libx264", rate=30)
    stream.width, stream.height, stream.pix_fmt = 320, 180, "yuv420p"
    for i in range(30):
        frame = av.VideoFrame.from_ndarray(np.full((180, 320, 3), i * 8, np.uint8), format="bgr24")
        for p in stream.encode(frame):
            out.mux(p)
    for p in stream.encode():
        out.mux(p)
    out.close()
    src = VideoFileSource(path, realtime=False)
    src.start(30)
    got = []
    while (f := src.latest()) is not None or not src.finished:
        if f is not None:
            got.append(f)
    src.stop()
    assert len(got) >= 25
    assert got[0].image.shape == (180, 320, 3)


def test_video_source_restart_has_no_stale_frame(tmp_path):
    import av

    path = tmp_path / "v.mp4"
    out = av.open(str(path), "w")
    stream = out.add_stream("libx264", rate=30)
    stream.width, stream.height, stream.pix_fmt = 64, 36, "yuv420p"
    for i in range(30):
        frame = av.VideoFrame.from_ndarray(
            np.full((36, 64, 3), 10 + i * 7, np.uint8), format="bgr24"
        )
        for p in stream.encode(frame):
            out.mux(p)
    for p in stream.encode():
        out.mux(p)
    out.close()
    src = VideoFileSource(path, realtime=True)
    src.start(30)
    import time

    time.sleep(0.3)  # leaves an unread frame behind
    src.stop()
    src.start(30)
    first = None
    while first is None:
        first = src.latest()
    src.stop()
    assert first.image.mean() < 20  # the restart begins at the first frame, not a stale one
