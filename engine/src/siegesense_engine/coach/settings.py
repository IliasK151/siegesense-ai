"""How and when the coach talks to the player."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class CoachSettings(BaseModel):
    voice_enabled: bool = True
    voice_name: str | None = None
    voice_rate: Annotated[float, Field(ge=0.7, le=1.4)] = 1.0
    voice_volume: Annotated[float, Field(ge=0, le=1)] = 1.0
    tip_frequency: Literal["every_death", "key_moments", "report_only"] = "every_death"
    overlay_enabled: bool = True
    overlay_corner: Literal["top_right", "top_left", "bottom_right", "bottom_left"] = "top_right"
    llm_enabled: bool = True
    llm_model: str | None = None
    ptt_key: Annotated[str, Field(min_length=1, max_length=32)] = "F9"
