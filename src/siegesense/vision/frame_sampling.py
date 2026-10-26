"""Reproducible local frame sampling for manual review and annotation.

OpenCV is optional. Source recordings are never modified or uploaded.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SampledFrame:
    # timestamp_ms is the requested seek-grid position, not a verified media PTS.
    timestamp_ms: int
    frame_index: int
    filename: str
    reported_position_ms: float | None = None


@dataclass(frozen=True, slots=True)
class SamplingReport:
    source_path: str
    source_sha256: str
    source_fps: float
    source_width: int
    source_height: int
    duration_ms: int
    start_ms: int
    end_ms: int
    interval_ms: int
    frames: tuple[SampledFrame, ...]
    timestamp_policy: str = (
        "timestamp_ms records requested seek-grid positions; reported_position_ms "
        "is OpenCV's post-read position and is not guaranteed to be a presentation timestamp"
    )
    schema_version: int = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sample_video_frames(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    start_ms: int = 0,
    end_ms: int | None = None,
    interval_ms: int = 1000,
    capture_factory: Any | None = None,
) -> SamplingReport:
    """Sample a validated time range to a separate folder and write a JSON manifest.

    capture_factory is injectable for tests and must expose write_image(path, frame).
    Timestamps are derived from the requested grid; frame indices use source FPS.
    """
    source = Path(source_path).expanduser().resolve()
    destination = Path(output_dir).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Source recording does not exist: {source}")
    if destination == source or destination == source.parent:
        raise ValueError("Choose a separate output directory, not the source recording's folder")
    if source in destination.parents:
        raise ValueError("Output directory cannot be inside the source file path")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Output directory must be empty to avoid overwriting previous samples")
    for name, value in (("start_ms", start_ms), ("interval_ms", interval_ms)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer number of milliseconds")
    if end_ms is not None and (
        isinstance(end_ms, bool) or not isinstance(end_ms, int)
    ):
        raise ValueError("end_ms must be an integer number of milliseconds")
    if start_ms < 0:
        raise ValueError("Start time must be zero or greater")
    if interval_ms <= 0:
        raise ValueError("Sampling interval must be greater than zero")

    if capture_factory is None:
        try:
            import cv2
        except ImportError as error:
            raise RuntimeError(
                "Frame sampling requires OpenCV. Install with: pip install -e .[vision]"
            ) from error
        capture_factory = cv2.VideoCapture
        image_writer = cv2.imwrite
        prop_fps, prop_width, prop_height, prop_frames, prop_msec = (
            cv2.CAP_PROP_FPS, cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT,
            cv2.CAP_PROP_FRAME_COUNT, cv2.CAP_PROP_POS_MSEC,
        )
    else:
        image_writer = getattr(capture_factory, "write_image", None)
        if image_writer is None:
            raise ValueError("Injected capture factory must provide write_image(path, frame)")
        prop_fps, prop_width, prop_height, prop_frames, prop_msec = 5, 3, 4, 7, 0

    capture = capture_factory(str(source))
    try:
        if not getattr(capture, "isOpened", lambda: True)():
            raise ValueError("Could not open the selected recording")
        fps = float(capture.get(prop_fps))
        width, height = int(capture.get(prop_width)), int(capture.get(prop_height))
        frame_count = int(capture.get(prop_frames))
        if fps <= 0 or width <= 0 or height <= 0 or frame_count <= 0:
            raise ValueError("Recording metadata is missing or invalid; cannot sample reliably")
        duration_ms = round(frame_count / fps * 1000)
        actual_end_ms = duration_ms if end_ms is None else end_ms
        if actual_end_ms <= start_ms:
            raise ValueError("End time must be greater than start time")
        if actual_end_ms > duration_ms:
            raise ValueError("End time exceeds the recording duration")

        destination.mkdir(parents=True, exist_ok=True)
        samples = []
        for timestamp_ms in range(start_ms, actual_end_ms, interval_ms):
            frame_index = min(frame_count - 1, round(timestamp_ms * fps / 1000))
            seek_ok = capture.set(prop_msec, timestamp_ms)
            if seek_ok is False:
                raise ValueError(f"Video backend rejected seek to {timestamp_ms} ms")
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(f"Could not read frame at requested {timestamp_ms} ms")
            reported_position = float(capture.get(prop_msec))
            if not (reported_position >= 0 and reported_position < float("inf")):
                reported_position = None
            filename = f"frame_{timestamp_ms:09d}ms.png"
            target = destination / filename
            if not image_writer(str(target), frame):
                raise OSError(f"Could not write sampled frame: {target}")
            samples.append(
                SampledFrame(
                    timestamp_ms=timestamp_ms,
                    frame_index=frame_index,
                    filename=filename,
                    reported_position_ms=reported_position,
                )
            )

        report = SamplingReport(
            source_path=str(source), source_sha256=_sha256(source), source_fps=fps,
            source_width=width, source_height=height, duration_ms=duration_ms,
            start_ms=start_ms, end_ms=actual_end_ms, interval_ms=interval_ms,
            frames=tuple(samples),
        )
        payload = {**asdict(report), "frames": [asdict(frame) for frame in report.frames]}
        (destination / "sampling_manifest.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        return report
    finally:
        capture.release()
