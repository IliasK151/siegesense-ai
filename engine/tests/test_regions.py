import numpy as np
import pytest
from pydantic import ValidationError

from siegesense_engine.hud.regions import Box, HudRegions, crop
from siegesense_engine.profile import Profile


def test_crop_pixels():
    frame = np.zeros((1080, 1920, 3), np.uint8)
    assert crop(frame, HudRegions().killfeed).shape == (238, 557, 3)


def test_crop_clamped():
    frame = np.zeros((100, 100, 3), np.uint8)
    out = crop(frame, Box(x=0.99, y=0.99, w=0.01, h=0.01))
    assert out.shape[0] >= 1 and out.shape[1] >= 1


@pytest.mark.parametrize(
    "kw",
    [dict(x=-0.1, y=0, w=0.1, h=0.1), dict(x=0.95, y=0, w=0.1, h=0.1), dict(x=0, y=0, w=0, h=0.1)],
)
def test_box_validation(kw):
    with pytest.raises(ValidationError):
        Box(**kw)


def test_old_profile_json_gets_defaults():
    old = '{"in_game_name":"Ash.Main","dpi":800,"yaw_sensitivity":10,"pitch_sensitivity":10}'
    p = Profile.model_validate_json(old)
    assert p.hud_regions == HudRegions()
    assert p.my_score_side == "left"
    assert p.capture_fps == 30


def test_capture_fps_range():
    with pytest.raises(ValidationError):
        Profile(in_game_name="Ash.Main", dpi=800, yaw_sensitivity=10, pitch_sensitivity=10,
                capture_fps=120)  # fmt: skip
