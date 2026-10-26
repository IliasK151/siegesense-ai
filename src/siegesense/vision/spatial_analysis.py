"""Descriptive geometry summaries for manually marked reticle and target points.

This module never detects either point. Coordinates are normalized to the full frame
and must be supplied by a human annotator.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from statistics import median


@dataclass(frozen=True, slots=True)
class SpatialError:
    annotation_id: str
    timestamp_ms: int
    horizontal_offset_pct: float
    vertical_offset_pct: float
    distance_pct_frame_diagonal: float


@dataclass(frozen=True, slots=True)
class SpatialErrorSummary:
    annotated_point_count: int
    excluded_without_both_points: int
    median_horizontal_offset_pct: float | None
    median_vertical_offset_pct: float | None
    median_distance_pct_frame_diagonal: float | None
    observations: tuple[SpatialError, ...]
    limitations: tuple[str, ...]


def summarize_spatial_error(dataset_path: str | Path) -> SpatialErrorSummary:
    """Summarize target-minus-reticle offsets for frames with both manual points.

    Horizontal/vertical offsets are percentages of frame width/height respectively.
    Distance is percentage of the frame diagonal. Positive horizontal means the
    target is right of the marked reticle; positive vertical means it is below it.
    """
    path = Path(dataset_path).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported annotation dataset schema version")
    annotations = payload.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("Annotation dataset annotations must be a list")

    observations: list[SpatialError] = []
    excluded = 0
    for annotation in annotations:
        if not isinstance(annotation, dict):
            raise ValueError("Each annotation entry must be an object")
        values = (annotation.get("reticle_x"), annotation.get("reticle_y"),
                  annotation.get("target_x"), annotation.get("target_y"))
        if all(value is None for value in values):
            excluded += 1
            continue
        if any(value is None for value in values):
            raise ValueError("Spatial analysis requires both reticle and target coordinate pairs")
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise ValueError("Spatial coordinates must be finite numbers between 0 and 1")
        dx = float(annotation["target_x"]) - float(annotation["reticle_x"])
        dy = float(annotation["target_y"]) - float(annotation["reticle_y"])
        distance = math.hypot(dx, dy) / math.sqrt(2) * 100
        observations.append(SpatialError(
            annotation_id=str(annotation.get("annotation_id", "")),
            timestamp_ms=annotation.get("timestamp_ms", 0),
            horizontal_offset_pct=round(dx * 100, 4),
            vertical_offset_pct=round(dy * 100, 4),
            distance_pct_frame_diagonal=round(distance, 4),
        ))

    limitations = (
        "Coordinates are manually marked; no reticle or opponent detector is used.",
        "Offsets describe visible point geometry, not mouse input, hit probability, or skill.",
        "Coordinate marking consistency and target-center choice affect the result.",
        "A still frame cannot establish overshoot, undershoot, or correction direction over time.",
        "Only annotations with both reticle and target points contribute to the summary.",
    )
    return SpatialErrorSummary(
        annotated_point_count=len(observations),
        excluded_without_both_points=excluded,
        median_horizontal_offset_pct=(
            round(median(item.horizontal_offset_pct for item in observations), 4)
            if observations else None
        ),
        median_vertical_offset_pct=(
            round(median(item.vertical_offset_pct for item in observations), 4)
            if observations else None
        ),
        median_distance_pct_frame_diagonal=(
            round(median(item.distance_pct_frame_diagonal for item in observations), 4)
            if observations else None
        ),
        observations=tuple(observations),
        limitations=limitations,
    )



def write_spatial_report(
    dataset_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Export manually marked reticle/target geometry as a transparent JSON report."""
    source = Path(dataset_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if output == source:
        raise ValueError("Spatial report output must not overwrite its annotation dataset")
    summary = summarize_spatial_error(source)
    report = {
        "schema_version": 1,
        "report_type": "manual_spatial_offset",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(source),
        "summary": {
            "annotated_point_count": summary.annotated_point_count,
            "excluded_without_both_points": summary.excluded_without_both_points,
            "median_horizontal_offset_pct": summary.median_horizontal_offset_pct,
            "median_vertical_offset_pct": summary.median_vertical_offset_pct,
            "median_distance_pct_frame_diagonal": summary.median_distance_pct_frame_diagonal,
        },
        "observations": [
            {
                "annotation_id": item.annotation_id,
                "timestamp_ms": item.timestamp_ms,
                "horizontal_offset_pct": item.horizontal_offset_pct,
                "vertical_offset_pct": item.vertical_offset_pct,
                "distance_pct_frame_diagonal": item.distance_pct_frame_diagonal,
            }
            for item in summary.observations
        ],
        "limitations": list(summary.limitations),
        "automatic_detection_used": False,
        "model_performance_evaluated": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temporary.replace(output)
    return output
