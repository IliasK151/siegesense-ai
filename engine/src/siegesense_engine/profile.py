"""The player's profile: identity, mouse settings and display settings."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

ADS_KEYS: tuple[str, ...] = ("1x", "2.5x", "3x", "4x", "5x", "12x")
WindowMode = Literal["fullscreen", "windowed", "borderless", "unknown"]
NAME_PATTERN = r"^[A-Za-z0-9._-]{3,15}$"


class Profile(BaseModel):
    in_game_name: Annotated[str, Field(pattern=NAME_PATTERN)]
    dpi: Annotated[int, Field(ge=100, le=32000)]
    yaw_sensitivity: Annotated[int, Field(ge=1, le=100)]
    pitch_sensitivity: Annotated[int, Field(ge=1, le=100)]
    mouse_multiplier_unit: Annotated[float, Field(gt=0, le=1)] = 0.02
    x_factor_aiming: Annotated[float, Field(gt=0, le=1)] = 0.02
    ads_sensitivity: dict[str, Annotated[int, Field(ge=1, le=200)]] = {}
    fov: Annotated[float, Field(ge=60, le=90)] = 75.0
    resolution_width: Annotated[int, Field(ge=640, le=7680)] = 1920
    resolution_height: Annotated[int, Field(ge=480, le=4320)] = 1080
    hud_scale: Annotated[int, Field(ge=50, le=100)] = 100
    window_mode: WindowMode = "unknown"
    counts_per_360: Annotated[float, Field(gt=0)] | None = None

    @field_validator("ads_sensitivity")
    @classmethod
    def _known_ads_keys(cls, value: dict[str, int]) -> dict[str, int]:
        unknown = sorted(set(value) - set(ADS_KEYS))
        if unknown:
            raise ValueError(f"unknown ADS scope(s): {', '.join(unknown)}")
        return value
