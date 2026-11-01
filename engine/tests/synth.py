"""Synthetic mouse traces for tests: human-like (minimum-jerk) flicks in degrees."""

from __future__ import annotations

import math

Sample = tuple[float, float, float]  # (t seconds, dx degrees, dy degrees)


def _segment(t0: float, amplitude: float, duration: float, angle_deg: float, rate_hz: int):
    n = max(1, round(duration * rate_hz))
    ux, uy = math.cos(math.radians(angle_deg)), -math.sin(math.radians(angle_deg))
    out: list[Sample] = []
    prev = 0.0
    for i in range(1, n + 1):
        s = i / n
        pos = amplitude * (10 * s**3 - 15 * s**4 + 6 * s**5)
        d = pos - prev
        prev = pos
        out.append((t0 + i / rate_hz, d * ux, d * uy))
    return out


def flick(
    t0: float,
    amplitude: float,
    duration: float,
    angle_deg: float = 0,
    rate_hz: int = 1000,
    overshoot: float = 0,
    correction_duration: float = 0.08,
) -> list[Sample]:
    """A flick of ``amplitude`` degrees, optionally corrected back by ``overshoot`` degrees."""
    samples = _segment(t0, amplitude, duration, angle_deg, rate_hz)
    if overshoot:
        samples += _segment(t0 + duration, -overshoot, correction_duration, angle_deg, rate_hz)
    return samples


def end_time(samples: list[Sample]) -> float:
    return samples[-1][0]
