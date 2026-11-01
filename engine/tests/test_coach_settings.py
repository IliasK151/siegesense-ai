import pytest
from pydantic import ValidationError

from siegesense_engine.coach.settings import CoachSettings
from siegesense_engine.profile import Profile


def test_defaults():
    c = CoachSettings()
    assert c.voice_enabled and c.tip_frequency == "every_death" and c.ptt_key == "F9"
    assert c.overlay_corner == "top_right" and c.llm_enabled and c.llm_model is None


def test_old_profile_gets_coach_defaults():
    old = '{"in_game_name":"Ash.Main","dpi":800,"yaw_sensitivity":10,"pitch_sensitivity":10}'
    assert Profile.model_validate_json(old).coach == CoachSettings()


@pytest.mark.parametrize(
    "kw", [{"voice_rate": 2.0}, {"voice_volume": -0.1}, {"tip_frequency": "always"}]
)
def test_validation(kw):
    with pytest.raises(ValidationError):
        CoachSettings(**kw)
