"""Local, schema-versioned annotations for sampled frames.

Annotations are human labels, not model predictions. The store is intentionally
small and file-based so datasets remain inspectable and portable.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ANNOTATION_SCHEMA_VERSION = 1
ALLOWED_LABELS = frozenset({
    "target_transition",
    "crosshair_on_target",
    "crosshair_off_target",
    "movement_start",
    "movement_stop",
    "ambiguous",
    "unusable_frame",
})


@dataclass(frozen=True, slots=True)
class FrameAnnotation:
    annotation_id: str
    timestamp_ms: int
    frame_filename: str
    label: str
    note: str
    annotator: str
    created_at: str


@dataclass(frozen=True, slots=True)
class AnnotationDataset:
    schema_version: int
    source_sha256: str
    manifest_path: str
    annotations: tuple[FrameAnnotation, ...]


def load_manifest(manifest_path: str | Path) -> dict:
    """Load and minimally validate a frame-sampling manifest."""
    path = Path(manifest_path).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported sampling manifest schema version")
    if not isinstance(payload.get("source_sha256"), str) or not payload["source_sha256"]:
        raise ValueError("Sampling manifest is missing its source fingerprint")
    if not isinstance(payload.get("frames"), list):
        raise ValueError("Sampling manifest has no frame list")
    for frame in payload["frames"]:
        if not isinstance(frame, dict) or not isinstance(frame.get("timestamp_ms"), int) or not isinstance(frame.get("filename"), str):
            raise ValueError("Sampling manifest contains an invalid frame entry")
    return payload


def load_dataset(dataset_path: str | Path) -> AnnotationDataset:
    """Read an annotation dataset and validate its schema and label values."""
    path = Path(dataset_path).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != ANNOTATION_SCHEMA_VERSION:
        raise ValueError("Unsupported annotation dataset schema version")
    annotations = tuple(FrameAnnotation(**item) for item in payload.get("annotations", []))
    for annotation in annotations:
        _validate_annotation_fields(annotation.timestamp_ms, annotation.label, annotation.annotator)
    return AnnotationDataset(
        schema_version=payload["schema_version"],
        source_sha256=payload["source_sha256"],
        manifest_path=payload["manifest_path"],
        annotations=annotations,
    )


def _validate_annotation_fields(timestamp_ms: int, label: str, annotator: str) -> None:
    if timestamp_ms < 0:
        raise ValueError("Annotation timestamp must be zero or greater")
    if label not in ALLOWED_LABELS:
        raise ValueError(f"Unsupported annotation label: {label}")
    if not annotator.strip():
        raise ValueError("Annotator name cannot be empty")


class AnnotationStore:
    """Append/update manual labels associated with one sampled-video manifest."""

    def __init__(self, manifest_path: str | Path, dataset_path: str | Path) -> None:
        self.manifest_path = Path(manifest_path).expanduser().resolve()
        self.dataset_path = Path(dataset_path).expanduser().resolve()
        self.manifest = load_manifest(self.manifest_path)
        if self.dataset_path == self.manifest_path:
            raise ValueError("Annotation dataset must not overwrite the sampling manifest")
        self._frames = {
            (frame["timestamp_ms"], frame["filename"])
            for frame in self.manifest["frames"]
        }
        self._annotations: dict[str, FrameAnnotation] = {}
        if self.dataset_path.exists():
            dataset = load_dataset(self.dataset_path)
            if dataset.source_sha256 != self.manifest["source_sha256"]:
                raise ValueError("Annotation dataset belongs to a different source recording")
            for annotation in dataset.annotations:
                self._validate_frame(annotation.timestamp_ms, annotation.frame_filename)
                self._annotations[annotation.annotation_id] = annotation

    @property
    def annotations(self) -> tuple[FrameAnnotation, ...]:
        return tuple(sorted(
            self._annotations.values(),
            key=lambda item: (item.timestamp_ms, item.created_at, item.annotation_id),
        ))

    def add(
        self,
        timestamp_ms: int,
        frame_filename: str,
        label: str,
        *,
        annotator: str,
        note: str = "",
    ) -> FrameAnnotation:
        _validate_annotation_fields(timestamp_ms, label, annotator)
        self._validate_frame(timestamp_ms, frame_filename)
        annotation = FrameAnnotation(
            annotation_id=str(uuid.uuid4()),
            timestamp_ms=timestamp_ms,
            frame_filename=frame_filename,
            label=label,
            note=note.strip(),
            annotator=annotator.strip(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._annotations[annotation.annotation_id] = annotation
        self.save()
        return annotation

    def remove(self, annotation_id: str) -> bool:
        """Remove one annotation and persist; return False if the ID was unknown."""
        if self._annotations.pop(annotation_id, None) is None:
            return False
        self.save()
        return True

    def save(self) -> None:
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": ANNOTATION_SCHEMA_VERSION,
            "source_sha256": self.manifest["source_sha256"],
            "manifest_path": str(self.manifest_path),
            "annotations": [asdict(item) for item in self.annotations],
        }
        temporary = self.dataset_path.with_suffix(self.dataset_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.dataset_path)

    def _validate_frame(self, timestamp_ms: int, frame_filename: str) -> None:
        if (timestamp_ms, frame_filename) not in self._frames:
            raise ValueError("Annotation must reference a frame in the selected manifest")
