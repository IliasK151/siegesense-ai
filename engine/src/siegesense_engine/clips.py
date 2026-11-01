"""Death clips (spec §4.7): the ring-buffer frames around a death, encoded to MP4, with the
player's input trace saved next to it. Disk use is capped; the oldest clips go first."""

from __future__ import annotations

import json
import logging
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)
DEFAULT_CAP = 5 * 1024**3


class ClipWriter:
    def __init__(self, directory: Path, cap_bytes: int = DEFAULT_CAP) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cap_bytes = cap_bytes

    def write(self, frames: list[tuple[float, bytes]], trace: list[dict], name: str) -> Path | None:
        path = self.dir / f"{name}.mp4"
        try:
            self._encode(frames, path)
        except Exception:
            log.exception("could not write clip %s", name)
            path.unlink(missing_ok=True)
            return None
        path.with_suffix(".json").write_text(json.dumps({"name": name, "trace": trace}))
        self._enforce_cap(keep=path)
        return path

    @staticmethod
    def _encode(frames: list[tuple[float, bytes]], path: Path) -> None:
        import av

        decoded: list[tuple[float, np.ndarray]] = []
        for t, data in frames:
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                decoded.append((t, img))
        if not decoded:
            raise ValueError("no decodable frames")
        h, w = decoded[0][1].shape[:2]
        w, h = w - w % 2, h - h % 2
        with av.open(str(path), "w") as out:
            stream = None
            # Two encoder threads: clips are saved while the next round is coming up.
            for codec, opts in (
                ("libx264", {"preset": "veryfast", "crf": "26", "threads": "2"}),
                ("mpeg4", {"threads": "2"}),
            ):
                try:
                    stream = out.add_stream(codec, rate=30, options=opts)
                    break
                except Exception:
                    continue
            if stream is None:
                raise RuntimeError("no video encoder available")
            stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
            stream.codec_context.time_base = Fraction(1, 1000)
            t0 = decoded[0][0]
            last_pts = -1
            for t, img in decoded:
                frame = av.VideoFrame.from_ndarray(img[:h, :w], format="bgr24")
                pts = max(int(round((t - t0) * 1000)), last_pts + 1)
                frame.pts, frame.time_base = pts, Fraction(1, 1000)
                last_pts = pts
                for packet in stream.encode(frame):
                    out.mux(packet)
            for packet in stream.encode():
                out.mux(packet)

    def _enforce_cap(self, keep: Path) -> None:
        clips = sorted(self.dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)

        def size(p: Path) -> int:
            j = p.with_suffix(".json")
            return p.stat().st_size + (j.stat().st_size if j.exists() else 0)

        total = sum(size(p) for p in clips)
        for p in clips:
            if total <= self.cap_bytes:
                break
            if p == keep:
                continue
            total -= size(p)
            p.unlink(missing_ok=True)
            p.with_suffix(".json").unlink(missing_ok=True)
