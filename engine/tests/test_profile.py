import json

import pytest
from pydantic import ValidationError

from siegesense_engine.profile import Profile


def valid_profile(protocol_fixtures) -> dict:
    env = json.loads((protocol_fixtures / "save_profile.json").read_text())
    return env["payload"]["profile"]


def test_fixture_profile_is_valid(protocol_fixtures):
    p = Profile.model_validate(valid_profile(protocol_fixtures))
    assert p.in_game_name == "Ash.Main"
    assert p.counts_per_360 is None


@pytest.mark.parametrize(
    "override",
    [
        {"dpi": 0},
        {"dpi": 40000},
        {"in_game_name": "ab"},
        {"in_game_name": "bad name!"},
        {"in_game_name": "a" * 16},
        {"yaw_sensitivity": 0},
        {"pitch_sensitivity": 101},
        {"fov": 120},
        {"ads_sensitivity": {"7x": 50}},
        {"ads_sensitivity": {"1x": 0}},
        {"hud_scale": 40},
        {"window_mode": "maximized"},
    ],
)
def test_profile_validation(protocol_fixtures, override):
    data = {**valid_profile(protocol_fixtures), **override}
    with pytest.raises(ValidationError):
        Profile.model_validate(data)


def test_defaults_fill_optional_fields():
    p = Profile(in_game_name="Thermite_1", dpi=400, yaw_sensitivity=15, pitch_sensitivity=15)
    assert p.fov == 75.0
    assert p.window_mode == "unknown"
    assert p.ads_sensitivity == {}
