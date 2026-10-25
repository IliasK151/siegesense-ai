"""Validation helpers for curated, human-labelled evaluation sets.

This module reports annotation coverage and guards against recording-level
train/evaluation leakage. It does not train or score a vision model.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

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



def write_evaluation_report(
    output_path: str | Path,
    datasets: Iterable[tuple[str, str | Path]],
    *,
    annotator_pairs: Iterable[tuple[str, str | Path, str | Path]] = (),
) -> Path:
    """Write a local JSON coverage/agreement report without model-performance claims."""
    dataset_entries = tuple(datasets)
    pair_entries = tuple(annotator_pairs)
    output = Path(output_path).expanduser().resolve()
    protected_inputs = {
        Path(path).expanduser().resolve()
        for _, path in dataset_entries
    }
    protected_inputs.update(
        Path(path).expanduser().resolve()
        for _, first, second in pair_entries
        for path in (first, second)
    )
    if output in protected_inputs:
        raise ValueError("Report output must not overwrite an annotation dataset")
    summaries = summarize_datasets(dataset_entries)
    agreements = []
    for name, first_path, second_path in pair_entries:
        if not name.strip():
            raise ValueError("Agreement report name cannot be empty")
        agreement = compare_annotators(first_path, second_path)
        agreements.append({"name": name, **asdict(agreement)})
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_type": "annotation_coverage_and_agreement",
        "model_performance_evaluated": False,
        "datasets": [asdict(summary) for summary in summaries],
        "annotator_agreement": agreements,
        "limitations": [
            "Agreement measures consistency, not correctness.",
            "No automatic detector was trained or scored by this report.",
            "Recording-level leakage checks cover the named datasets supplied.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temporary.replace(output)
    return output
