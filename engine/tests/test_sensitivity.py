import pytest

from siegesense_engine.mechanics.sensitivity import (
    cm_per_360,
    conversion,
    estimated_counts_per_360,
)
from siegesense_engine.profile import Profile


def prof(**kw) -> Profile:
    base = dict(in_game_name="Ash.Main", dpi=800, yaw_sensitivity=10, pitch_sensitivity=10)
    return Profile(**{**base, **kw})


def test_estimated_conversion():
    c = conversion(prof())
    assert c.yaw == pytest.approx(0.0572957795, abs=1e-9)
    assert c.pitch == pytest.approx(0.0572957795, abs=1e-9)
    assert c.source == "estimated"


def test_calibrated_conversion():
    c = conversion(prof(counts_per_360=36000, pitch_sensitivity=5))
    assert c.yaw == pytest.approx(0.01)
    assert c.pitch == pytest.approx(0.005)
    assert c.source == "calibrated"


def test_estimated_counts_per_360():
    assert estimated_counts_per_360(prof()) == pytest.approx(360 / 0.0572957795, rel=1e-6)


def test_cm_per_360():
    assert cm_per_360(prof(counts_per_360=36000)) == pytest.approx(114.3)


def test_estimate_matches_standard_converters():
    # Siege yaw is 0.00572957795 deg/count per sensitivity point at the default 0.02 multiplier:
    # sens 10 at 800 DPI is about 19.9 cm/360 (not ~100 cm).
    p = prof()
    assert conversion(p).yaw == pytest.approx(10 * 0.00572957795, rel=1e-6)
    assert cm_per_360(p) == pytest.approx(19.95, abs=0.1)


def test_estimate_scales_with_multiplier():
    assert conversion(prof(mouse_multiplier_unit=0.04)).yaw == pytest.approx(
        2 * conversion(prof()).yaw
    )
