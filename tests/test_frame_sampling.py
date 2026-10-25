"""Tests for deterministic local video frame sampling."""
import json
from pathlib import Path

import pytest

from siegesense.vision.frame_sampling import sample_video_frames


class FakeCapture:
    def __init__(self, _path: str) -> None:
        self.position_ms = 0
        self.released = False

    def isOpened(self) -> bool:
        return True

    def get(self, prop: int) -> float:
        if prop == 0:
            return float(self.position_ms)
        return {5: 10.0, 3: 1920.0, 4: 1080.0, 7: 100.0}.get(prop, 0.0)

    def set(self, _prop: int, value: float) -> bool:
        self.position_ms = int(value)
        return True

    def read(self):
        return True, {"timestamp_ms": self.position_ms}

    def release(self) -> None:
        self.released = True


class FakeCaptureFactory:
    last_capture: FakeCapture | None = None

    def __new__(cls, path: str) -> FakeCapture:
        cls.last_capture = FakeCapture(path)
        return cls.last_capture

    @staticmethod
    def write_image(path: str, _frame: object) -> bool:
        Path(path).write_bytes(b"fake-frame")
        return True


def test_sampling_writes_frames_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake source recording")
    output = tmp_path / "sampled-frames"
    report = sample_video_frames(
        source, output, start_ms=1000, end_ms=4000, interval_ms=1000,
        capture_factory=FakeCaptureFactory,
    )
    assert [frame.timestamp_ms for frame in report.frames] == [1000, 2000, 3000]
    assert [frame.frame_index for frame in report.frames] == [10, 20, 30]
    assert all((output / frame.filename).is_file() for frame in report.frames)
    manifest = json.loads((output / "sampling_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["source_sha256"] == report.source_sha256
    assert manifest["source_fps"] == 10.0
    assert "requested seek-grid positions" in manifest["timestamp_policy"]
    assert [frame["reported_position_ms"] for frame in manifest["frames"]] == [1000.0, 2000.0, 3000.0]
    assert FakeCaptureFactory.last_capture is not None
    assert FakeCaptureFactory.last_capture.released


def test_sampling_rejects_invalid_ranges(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake source recording")
    with pytest.raises(ValueError, match="greater than zero"):
        sample_video_frames(source, tmp_path / "frames", interval_ms=0,
                            capture_factory=FakeCaptureFactory)
    with pytest.raises(ValueError, match="greater than start"):
        sample_video_frames(source, tmp_path / "frames", start_ms=3000, end_ms=3000,
                            capture_factory=FakeCaptureFactory)
    with pytest.raises(ValueError, match="exceeds"):
        sample_video_frames(source, tmp_path / "frames", end_ms=12000,
                            capture_factory=FakeCaptureFactory)


def test_sampling_rejects_missing_recording(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        sample_video_frames(tmp_path / "missing.mp4", tmp_path / "frames",
                            capture_factory=FakeCaptureFactory)



def test_sampling_refuses_to_overwrite_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake source recording")
    output = tmp_path / "frames"
    output.mkdir()
    existing = output / "keep.txt"
    existing.write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        sample_video_frames(source, output, capture_factory=FakeCaptureFactory)
    assert existing.read_text(encoding="utf-8") == "do not overwrite"



def test_sampling_rejects_non_integer_timing_values(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake source recording")
    with pytest.raises(ValueError, match="integer"):
        sample_video_frames(source, tmp_path / "float-interval", interval_ms=100.5,
                            capture_factory=FakeCaptureFactory)
    with pytest.raises(ValueError, match="integer"):
        sample_video_frames(source, tmp_path / "bool-start", start_ms=True,
                            capture_factory=FakeCaptureFactory)
