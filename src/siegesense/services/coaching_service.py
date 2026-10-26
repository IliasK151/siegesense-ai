"""Transparent coaching insights derived only from explicit manual review tags.

This is deterministic evidence aggregation, not a trained AI model and not a visual
detector. It never infers a problem from free-text notes alone.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from siegesense.domain.models import Observation, Session

# Keep this list aligned with the tag examples shown in Session Review.
COACHING_TAG_GUIDE: tuple[str, ...] = (
    "overflick",
    "underflick",
    "target-switch",
    "crosshair-placement",
    "correction",
    "recoil",
    "movement",
    "positioning",
    "decision",
)


@dataclass(frozen=True, slots=True)
class CoachingInsight:
    """A review prompt with its source evidence and a controlled practice suggestion."""

    key: str
    title: str
    observation_count: int
    session_count: int
    evidence_level: str
    summary: str
    drill: str
    evidence: tuple[tuple[Session, Observation], ...]


_RULES: dict[str, tuple[str, str]] = {
    "overflick": (
        "Possible overflick / overshoot",
        "In the next 10 comparable target transitions, keep your current sensitivity. "
        "Record the first reticle endpoint before correcting, using the same scope and "
        "similar target distance. Count a pass only when the reticle visibly crosses "
        "past the intended target.",
    ),
    "underflick": (
        "Possible underflick / undershoot",
        "In the next 10 comparable target transitions, keep your current sensitivity. "
        "Record whether the first reticle endpoint stops short before correcting. "
        "Keep scope and target distance as similar as practical.",
    ),
    "target-switch": (
        "Target-switch consistency",
        "Review 10 moments where you transfer between threats. Before moving, identify "
        "the intended next target; then record whether the reticle arrived, needed a "
        "correction, or the situation forced a different choice.",
    ),
    "crosshair-placement": (
        "Pre-aim and crosshair placement",
        "Review 10 entries or common angles. Before seeing an opponent, note whether "
        "the reticle was already at the expected head/upper-torso height and near the "
        "likely angle. Keep pre-aim placement separate from reactive flick performance.",
    ),
    "correction": (
        "First movement versus correction",
        "For 10 target acquisitions, note the first endpoint and how many visible "
        "corrections followed. Do not change sensitivity until you can separate an "
        "initial overshoot from a late target read or deliberate tracking correction.",
    ),
    "recoil-control": (
        "Recoil-control review",
        "Use a short, repeatable practice block with the same weapon, attachment, and "
        "distance. Record burst length and whether the grouping stays controllable; "
        "review recoil separately from target-acquisition events.",
    ),
    "movement-exposure": (
        "Peeking and movement exposure",
        "Review five similar peeks. Identify the intended cover, when your body becomes "
        "visible, and whether you exposed to more than one angle. Test one change to "
        "timing or path while keeping the rest of the situation comparable.",
    ),
    "positioning": (
        "Positioning and available cover",
        "Before the next five engagements, name your nearest usable cover and exit path. "
        "After review, note whether the chosen angle gave you information without "
        "forcing an unnecessary second exposure.",
    ),
    "decision-making": (
        "Decision review",
        "Choose three timestamped decisions. Write what information was available at "
        "that moment, what you chose, and one alternative. Judge the decision from the "
        "information available then—not from the round outcome alone.",
    ),
}

_ALIASES: dict[str, str] = {
    "overflick": "overflick",
    "over flick": "overflick",
    "overshoot": "overflick",
    "overshot": "overflick",
    "overshooting": "overflick",
    "underflick": "underflick",
    "under flick": "underflick",
    "undershoot": "underflick",
    "undershot": "underflick",
    "undershooting": "underflick",
    "target switch": "target-switch",
    "target switching": "target-switch",
    "switch target": "target-switch",
    "target transition": "target-switch",
    "target transitions": "target-switch",
    "crosshair placement": "crosshair-placement",
    "pre aim": "crosshair-placement",
    "preaim": "crosshair-placement",
    "placement": "crosshair-placement",
    "correction": "correction",
    "micro correction": "correction",
    "micro corrections": "correction",
    "double correction": "correction",
    "recoil": "recoil-control",
    "recoil control": "recoil-control",
    "spray control": "recoil-control",
    "movement": "movement-exposure",
    "peek": "movement-exposure",
    "peeking": "movement-exposure",
    "wide peek": "movement-exposure",
    "overpeek": "movement-exposure",
    "over peek": "movement-exposure",
    "movement exposure": "movement-exposure",
    "positioning": "positioning",
    "cover": "positioning",
    "angle": "positioning",
    "decision": "decision-making",
    "decision making": "decision-making",
    "timing decision": "decision-making",
}


def _canonical_tag(tag: str) -> str | None:
    """Resolve a manually supplied tag; unknown tags do not create coaching claims."""
    normalized = " ".join(tag.casefold().strip().replace("_", " ").replace("-", " ").split())
    return _ALIASES.get(normalized)


def build_coaching_insights(
    records: Iterable[tuple[Session, Observation]],
) -> list[CoachingInsight]:
    """Aggregate explicitly tagged observations into cautious, actionable review prompts.

    One observation is counted at most once for a given coaching issue, even if the
    user supplied two aliases for it. No inference is made from observation text.
    """
    grouped: dict[str, dict[str, tuple[Session, Observation]]] = defaultdict(dict)
    for session, observation in records:
        for tag in set(observation.tags):
            key = _canonical_tag(tag)
            if key is not None:
                grouped[key][observation.id] = (session, observation)

    insights: list[CoachingInsight] = []
    for key, by_observation in grouped.items():
        evidence = tuple(
            sorted(
                by_observation.values(),
                key=lambda pair: (pair[0].started_at, pair[1].timestamp_ms, pair[1].id),
                reverse=True,
            )
        )
        observation_count = len(evidence)
        session_count = len({session.id for session, _observation in evidence})
        if observation_count == 1:
            evidence_level = "Single note"
            summary = (
                "One manually tagged instance. Treat this as a question to review, "
                "not a demonstrated weakness."
            )
        elif session_count == 1:
            evidence_level = "Repeated in one session"
            summary = (
                f"{observation_count} tagged observations appear in one session. "
                "Check whether this recurs in another match before changing settings."
            )
        else:
            evidence_level = "Recurring across sessions"
            summary = (
                f"{observation_count} tagged observations span {session_count} sessions. "
                "This is worth testing in a controlled practice block, not proof of cause."
            )
        title, drill = _RULES[key]
        insights.append(
            CoachingInsight(
                key=key,
                title=title,
                observation_count=observation_count,
                session_count=session_count,
                evidence_level=evidence_level,
                summary=summary,
                drill=drill,
                evidence=evidence,
            )
        )
    return sorted(
        insights,
        key=lambda item: (-item.observation_count, -item.session_count, item.title),
    )
