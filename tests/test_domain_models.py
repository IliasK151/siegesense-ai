"""Validation tests for domain models."""

import pytest

from siegesense.domain.models import (
    MetricResult,
    Observation,
    ObservationKind,
    Session,
    SettingsExperiment,
)


def test_session_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="negative"):
        Session(duration_ms=-1)


def test_observation_rejects_negative_timestamp() -> None:
    with pytest.raises(ValueError, match="negative"):
        Observation(session_id="s1", timestamp_ms=-1, text="overshot")


def test_observation_requires_nonblank_text() -> None:
    with pytest.raises(ValueError, match="empty"):
        Observation(session_id="s1", timestamp_ms=1200, text="  ")


def test_metric_can_represent_missing_value_without_zero() -> None:
    metric = MetricResult(name="transition error", unit="px", source="recording", method="not measured", value=None, validity="missing")
    assert metric.value is None
    assert metric.validity == "missing"


def test_metric_requires_source_and_method() -> None:
    with pytest.raises(ValueError, match="source"):
        MetricResult(name="accuracy", unit="%", source="", method="manual", value=50, validity="valid")


def test_metric_confidence_is_bounded() -> None:
    with pytest.raises(ValueError, match="confidence"):
        MetricResult(name="accuracy", unit="%", source="manual", method="count", value=50, validity="valid", confidence=1.5)


def test_experiment_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="status"):
        SettingsExperiment(title="Test", hypothesis="Maybe better", baseline_snapshot_id="base", status="magic")


def test_observation_kind_values_are_explicit() -> None:
    assert ObservationKind.AIM.value == "aim"
