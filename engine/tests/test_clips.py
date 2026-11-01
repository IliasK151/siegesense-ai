import json
import os

import av
import cv2
import numpy as np

from siegesense_engine.clips import ClipWriter


def jpeg_frames(seconds=2.0, fps=30, size=(320, 180)):
    out = []
    for i in range(int(seconds * fps)):
        img = np.full((size[1], size[0], 3), (i * 4) % 255, np.uint8)
        cv2.putText(img, str(i), (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        out.append((100.0 + i / fps, cv2.imencode(".jpg", img)[1].tobytes()))
    return out


def test_clip_written(tmp_path):
    writer = ClipWriter(tmp_path)
    path = writer.write(jpeg_frames(), [{"t": 0, "yaw": 1.0}], "r1-death")
    assert path is not None and path.suffix == ".mp4"
    with av.open(str(path)) as c:
        n = sum(1 for _ in c.decode(c.streams.video[0]))
        duration = float(c.duration) / av.time_base
    assert n >= 50
    assert 1.7 <= duration <= 2.3
    trace = json.loads(path.with_suffix(".json").read_text())
    assert trace["trace"] == [{"t": 0, "yaw": 1.0}]


def test_disk_cap(tmp_path):
    writer = ClipWriter(tmp_path, cap_bytes=1)
    first = writer.write(jpeg_frames(0.5), [], "a")
    os.utime(first, (1, 1))
    os.utime(first.with_suffix(".json"), (1, 1))
    second = writer.write(jpeg_frames(0.5), [], "b")
    assert not first.exists() and not first.with_suffix(".json").exists()
    assert second.exists()  # the newest clip is always kept


def test_encode_failure_keeps_death(tmp_path):
    writer = ClipWriter(tmp_path)
    assert writer.write([], [], "empty") is None
    assert writer.write([(1.0, b"not a jpeg")], [], "broken") is None
    assert list(tmp_path.glob("*.mp4")) == []
