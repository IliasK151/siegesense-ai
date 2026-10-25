"""Validation helpers for curated, human-labelled evaluation sets.

This module reports annotation coverage and guards against recording-level
train/evaluation leakage. It does not train or score a vision model.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from siegesense.vision.annotations import ALLOWED_LABELS, load_dataset


@dataclass(frozen=True, slots=True)
class AgreementSummary:
    source_sha256: str
    overlapping_frames: int
    exact_agreement: int
    observed_agreement: float
    cohens_kappa: float | None


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    dataset_name: str
    recording_count: int
    annotation_count: int
    label_counts: dict[str, int]


def summarize_datasets(
    datasets: Iterable[tuple[str, str | Path]],
) -> tuple[DatasetSummary, ...]:
    """Summarize annotation coverage and reject recording-level leakage."""
    summaries: list[DatasetSummary] = []
    seen_sources: dict[str, str] = {}
    for name, dataset_path in datasets:
        if not name.strip():
            raise ValueError("Dataset name cannot be empty")
        dataset = load_dataset(dataset_path)
        source = dataset.source_sha256
        previous = seen_sources.get(source)
        if previous is not None:
            raise ValueError(
                f"Recording leakage: source fingerprint appears in both "
                f"'{previous}' and '{name}'"
            )
        seen_sources[source] = name
        counts = Counter(annotation.label for annotation in dataset.annotations)
        summaries.append(
            DatasetSummary(
                dataset_name=name,
                recording_count=1,
                annotation_count=len(dataset.annotations),
                label_counts={label: counts[label] for label in sorted(ALLOWED_LABELS)},
            )
        )
    return tuple(summaries)


def compare_annotators(
    first_path: str | Path,
    second_path: str | Path,
) -> AgreementSummary:
    """Compare two human-labelled datasets on the exact same sampled frames."""
    first = load_dataset(first_path)
    second = load_dataset(second_path)
    if first.source_sha256 != second.source_sha256:
        raise ValueError("Annotator datasets must reference the same source recording")
    first_labels = {
        (item.timestamp_ms, item.frame_filename): item.label
        for item in first.annotations
    }
    second_labels = {
        (item.timestamp_ms, item.frame_filename): item.label
        for item in second.annotations
    }
    common_frames = sorted(first_labels.keys() & second_labels.keys())
    if not common_frames:
        raise ValueError("Annotator datasets have no overlapping labelled frames")
    count = len(common_frames)
    exact = sum(first_labels[frame] == second_labels[frame] for frame in common_frames)
    observed = exact / count
    first_counts = Counter(first_labels[frame] for frame in common_frames)
    second_counts = Counter(second_labels[frame] for frame in common_frames)
    expected = sum(
        first_counts[label] * second_counts[label] for label in ALLOWED_LABELS
    ) / (count * count)
    denominator = 1.0 - expected
    kappa = (observed - expected) / denominator if denominator else None
    return AgreementSummary(
        source_sha256=first.source_sha256,
        overlapping_frames=count,
        exact_agreement=exact,
        observed_agreement=observed,
        cohens_kappa=kappa,
    )
