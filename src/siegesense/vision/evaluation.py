"""Validation helpers for curated, human-labelled evaluation sets.

This module reports annotation coverage and guards against recording-level
train/evaluation leakage. It does not train or score a vision model.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from siegesense.vision.annotations import ALLOWED_LABELS, load_dataset


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
