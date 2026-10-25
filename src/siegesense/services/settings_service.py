"""Application service for recording settings snapshots and experiments."""

from __future__ import annotations

from typing import Any

from siegesense.domain.models import SettingsExperiment, SettingsSnapshot
from siegesense.storage.database import Database


class SettingsService:
    """Coordinate settings comparisons without coupling the UI to SQL."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def save_snapshot(
        self,
        label: str,
        values: dict[str, Any],
        *,
        is_demo: bool = False,
    ) -> SettingsSnapshot:
        """Persist a labelled settings snapshot."""
        snapshot = SettingsSnapshot(label=label, values=values, is_demo=is_demo)
        self._database.add_settings_snapshot(snapshot)
        return snapshot

    def create_experiment(
        self,
        title: str,
        hypothesis: str,
        baseline_snapshot_id: str,
        *,
        changed_variable: str = "",
        test_snapshot_id: str | None = None,
        notes: str = "",
        is_demo: bool = False,
    ) -> SettingsExperiment:
        """Create an experiment linked to explicit baseline and test snapshots.

        When a test snapshot is supplied, require it to differ from the baseline
        in exactly one setting. This keeps the Settings Lab's one-variable-at-a-
        time promise enforceable rather than merely advisory.
        """
        if test_snapshot_id is not None:
            baseline = self._database.get_settings_snapshot(baseline_snapshot_id)
            test = self._database.get_settings_snapshot(test_snapshot_id)
            if baseline is None:
                raise ValueError("Baseline settings snapshot does not exist")
            if test is None:
                raise ValueError("Test settings snapshot does not exist")
            if baseline.is_demo != is_demo or test.is_demo != is_demo:
                raise ValueError("Experiment and snapshots must share demo provenance")
            keys = set(baseline.values) | set(test.values)
            changed_keys = [
                key for key in keys
                if key not in baseline.values
                or key not in test.values
                or baseline.values[key] != test.values[key]
            ]
            if not changed_keys:
                raise ValueError("Baseline and test snapshots are identical; change one setting before recording the experiment")
            if len(changed_keys) > 1:
                raise ValueError(
                    "One-variable experiments require exactly one changed setting; "
                    f"these snapshots differ in {len(changed_keys)} settings"
                )
        experiment = SettingsExperiment(
            title=title,
            hypothesis=hypothesis,
            baseline_snapshot_id=baseline_snapshot_id,
            changed_variable=changed_variable,
            test_snapshot_id=test_snapshot_id,
            notes=notes,
            is_demo=is_demo,
        )
        self._database.add_experiment(experiment)
        return experiment

    def update_experiment(
        self,
        experiment_id: str,
        *,
        status: str,
        outcome: str | None = None,
        notes: str | None = None,
    ) -> SettingsExperiment:
        """Record an experiment's current status and observed outcome."""
        return self._database.update_experiment(
            experiment_id, status=status, outcome=outcome, notes=notes
        )

    def list_snapshots(self, *, include_demo: bool = False) -> list[SettingsSnapshot]:
        return self._database.list_settings_snapshots(include_demo=include_demo)

    def list_experiments(self, *, include_demo: bool = False) -> list[SettingsExperiment]:
        return self._database.list_experiments(include_demo=include_demo)
