"""Tests for local screen-space motion estimates and report safeguards."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from siegesense.vision.motion_analysis import (
    _percentile,
    analyze_manifest_motion,
    write_motion_report,
)


def _write_manifest(root: Path, *, frames: list[dict], interval_ms: int = 100) -> Path:
    path = root / "sampling_manifest.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "source_sha256": "source-fingerprint",
            "interval_ms": interval_ms,
            "frames": frames,
        }),
        encoding="utf-8",
    )
    return path


def test_percentile_interpolates_and_rejects_empty_values() -> None:
    assert _percentile([0, 10], 50) == 5
    assert _percentile([1, 3, 5], 90) == pytest.approx(4.6)
    with pytest.raises(ValueError, match="empty"):
        _percentile([], 50)


def test_motion_analysis_rejects_manifest_path_traversal(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        frames=[
            {"timestamp_ms": 0, "filename": "frame_000.png"},
            {"timestamp_ms": 100, "filename": "../outside.png"},
        ],
    )
    with pytest.raises(ValueError, match="invalid frame entry"):
        analyze_manifest_motion(manifest)

    windows_manifest = _write_manifest(
        tmp_path,
        frames=[
            {"timestamp_ms": 0, "filename": "frame_000.png"},
            {"timestamp_ms": 100, "filename": r"..\\outside.png"},
        ],
    )
    with pytest.raises(ValueError, match="invalid frame entry"):
        analyze_manifest_motion(windows_manifest)


def test_motion_analysis_requires_known_sampling_interval(tmp_path: Path) -> None:
    manifest = tmp_path / "sampling_manifest.json"
    manifest.write_text(
        json.dumps({
            "schema_version": 1,
            "source_sha256": "source-fingerprint",
            "frames": [{"timestamp_ms": 0, "filename": "a.png"}],
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="positive interval_ms"):
        analyze_manifest_motion(manifest)


def test_motion_analysis_reports_shifted_synthetic_frames(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    first = np.zeros((160, 240), dtype=np.uint8)
    # Multiple corners give sparse optical flow enough stable features to track.
    for y in range(20, 140, 20):
        for x in range(20, 220, 20):
            cv2.rectangle(first, (x, y), (x + 6, y + 6), 255, -1)
    matrix = np.float32([[1, 0, 5], [0, 1, 3]])
    second = cv2.warpAffine(first, matrix, (240, 160))
    assert cv2.imwrite(str(tmp_path / "frame_000.png"), first)
    assert cv2.imwrite(str(tmp_path / "frame_100.png"), second)
    manifest = _write_manifest(
        tmp_path,
        frames=[
            {"timestamp_ms": 0, "filename": "frame_000.png"},
            {"timestamp_ms": 100, "filename": "frame_100.png"},
        ],
    )

    report = analyze_manifest_motion(manifest, cv2_module=cv2)

    assert report.frame_count == 2
    assert report.eligible_pair_count == 1
    assert report.analyzed_pair_count == 1
    assert report.median_motion_px_per_sample is not None
    assert report.median_motion_px_per_sample > 0
    assert report.pairs[0].coherent_feature_ratio >= 0.5
    assert any("does not measure mouse input" in item for item in report.limitations)
    target = write_motion_report(report, tmp_path / "motion.json")
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 1
    assert len(saved["pairs"]) == 1
    with pytest.raises(ValueError, match="cannot overwrite"):
        write_motion_report(report, manifest)
