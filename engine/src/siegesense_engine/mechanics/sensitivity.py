"""Converting raw mouse counts into in-game degrees.

Calibration (``counts_per_360``) is ground truth. Without it we use the community formula
for Siege: degrees per count = sensitivity × MouseSensitivityMultiplierUnit × 0.0572957795.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..profile import Profile

RAD_TO_DEG_MILLI = 0.0572957795


@dataclass(frozen=True)
class Conversion:
    yaw: float  # degrees per count, horizontal
    pitch: float  # degrees per count, vertical
    source: Literal["calibrated", "estimated"]


def _estimated_yaw(profile: Profile) -> float:
    return profile.yaw_sensitivity * profile.mouse_multiplier_unit * RAD_TO_DEG_MILLI


def conversion(profile: Profile) -> Conversion:
    ratio = profile.pitch_sensitivity / profile.yaw_sensitivity
    if profile.counts_per_360:
        yaw = 360.0 / profile.counts_per_360
        return Conversion(yaw=yaw, pitch=yaw * ratio, source="calibrated")
    yaw = _estimated_yaw(profile)
    return Conversion(yaw=yaw, pitch=yaw * ratio, source="estimated")


def estimated_counts_per_360(profile: Profile) -> float:
    return 360.0 / _estimated_yaw(profile)


def cm_per_360(profile: Profile) -> float:
    counts = profile.counts_per_360 or estimated_counts_per_360(profile)
    return counts / profile.dpi * 2.54
