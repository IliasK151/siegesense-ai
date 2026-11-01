"""Where each HUD element sits on screen, as normalised boxes (0..1) the player can adjust."""

from __future__ import annotations

from typing import Annotated

import numpy as np
from pydantic import BaseModel, Field, model_validator

Unit = Annotated[float, Field(ge=0, le=1)]
Size = Annotated[float, Field(gt=0, le=1)]


class Box(BaseModel):
    x: Unit
    y: Unit
    w: Size
    h: Size

    @model_validator(mode="after")
    def _inside(self) -> Box:
        if self.x + self.w > 1.0001 or self.y + self.h > 1.0001:
            raise ValueError("box must fit inside the screen")
        return self


class HudRegions(BaseModel):
    killfeed: Box = Box(x=0.70, y=0.08, w=0.29, h=0.22)
    timer: Box = Box(x=0.47, y=0.015, w=0.06, h=0.045)
    score_left: Box = Box(x=0.42, y=0.015, w=0.04, h=0.045)
    score_right: Box = Box(x=0.54, y=0.015, w=0.04, h=0.045)
    health: Box = Box(x=0.02, y=0.88, w=0.07, h=0.07)
    centre: Box = Box(x=0.40, y=0.40, w=0.20, h=0.20)


def crop(frame: np.ndarray, box: Box) -> np.ndarray:
    """Pixel crop of ``box``; clamped to the frame and never empty."""
    h, w = frame.shape[:2]
    x0 = min(max(int(round(box.x * w)), 0), w - 1)
    y0 = min(max(int(round(box.y * h)), 0), h - 1)
    x1 = min(max(int(round((box.x + box.w) * w)), x0 + 1), w)
    y1 = min(max(int(round((box.y + box.h) * h)), y0 + 1), h)
    return frame[y0:y1, x0:x1]
