"""Renders synthetic Siege-like HUD frames for tests (no real game art is used)."""

from __future__ import annotations

import cv2
import numpy as np

from siegesense_engine.hud.regions import Box, HudRegions

BLUE = (255, 160, 40)  # BGR
ORANGE = (40, 140, 255)
WHITE = (235, 235, 235)
TEAM = {"blue": BLUE, "orange": ORANGE}


def _px(box: Box, size):
    w, h = size
    return int(box.x * w), int(box.y * h), int(box.w * w), int(box.h * h)


def _text_in(img, text, box: Box, size, color=WHITE, scale_k=0.75):
    x, y, w, h = _px(box, size)
    scale = h / 40 * scale_k
    thick = max(1, int(round(scale * 2)))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    cv2.putText(
        img, text, (x + (w - tw) // 2, y + (h + th) // 2), cv2.FONT_HERSHEY_SIMPLEX,
        scale, color, thick, cv2.LINE_AA,
    )  # fmt: skip


def render(state: dict, size=(1920, 1080), regions: HudRegions | None = None) -> np.ndarray:
    """state keys: timer (seconds|None), score=(left,right)|None, health (int|None),
    kills=[(killer, killer_team, victim, victim_team), ...] newest first."""
    regions = regions or HudRegions()
    w, h = size
    img = np.full((h, w, 3), 28, np.uint8)
    # some scene texture so frames are not trivially empty
    cv2.rectangle(img, (0, int(h * 0.6)), (w, h), (40, 46, 52), -1)
    if state.get("timer") is not None:
        t = int(state["timer"])
        _text_in(img, f"{t // 60}:{t % 60:02d}", regions.timer, size)
    if state.get("score") is not None:
        left, right = state["score"]
        _text_in(img, str(left), regions.score_left, size, BLUE)
        _text_in(img, str(right), regions.score_right, size, ORANGE)
    if state.get("health") is not None:
        _text_in(img, str(state["health"]), regions.health, size)
    kx, ky, kw, _ = _px(regions.killfeed, size)
    line_h = int(h * 0.045)
    scale = line_h / 40 * 0.8
    thick = max(1, int(round(scale * 2)))
    for i, (killer, kt, victim, vt) in enumerate(state.get("kills", [])):
        base = ky + i * line_h + int(line_h * 0.7)
        (vw, _), _ = cv2.getTextSize(victim, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        (kw_, _), _ = cv2.getTextSize(killer, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        right = kx + kw - 6
        vx = right - vw
        icon_x = vx - int(line_h * 1.1)
        kxp = icon_x - int(line_h * 0.5) - kw_
        cv2.putText(img, killer, (kxp, base), cv2.FONT_HERSHEY_SIMPLEX, scale, TEAM[kt], thick,
                    cv2.LINE_AA)  # fmt: skip
        cv2.rectangle(img, (icon_x, base - int(line_h * 0.5)),
                      (icon_x + int(line_h * 0.6), base - 2), WHITE, -1)  # fmt: skip
        cv2.putText(img, victim, (vx, base), cv2.FONT_HERSHEY_SIMPLEX, scale, TEAM[vt], thick,
                    cv2.LINE_AA)  # fmt: skip
    return img


def render_bright(state: dict, size=(1920, 1080), regions: HudRegions | None = None) -> np.ndarray:
    """Like render(), but with a bright, textured sky behind the HUD and the dark translucent
    boxes Siege draws behind kill-feed entries."""
    regions = regions or HudRegions()
    img = render({**state, "kills": []}, size, regions)
    w, h = size
    sky = np.linspace(200, 245, h // 2, dtype=np.uint8)[:, None, None]
    img[: h // 2] = np.clip(
        np.broadcast_to(sky, (h // 2, w, 3))
        + np.random.default_rng(3).integers(-8, 8, (h // 2, w, 3)),
        0,
        255,
    ).astype(np.uint8)
    kx, ky, kw, _ = _px(regions.killfeed, size)
    line_h = int(h * 0.045)
    for i in range(len(state.get("kills", []))):
        y0 = ky + i * line_h + 2
        box = img[y0 : y0 + line_h - 4, kx + kw // 3 : kx + kw]
        img[y0 : y0 + line_h - 4, kx + kw // 3 : kx + kw] = (box * 0.25).astype(np.uint8)
    overlay = render({"kills": state.get("kills", [])}, size, regions)
    feed = overlay[ky : ky + int(regions.killfeed.h * h), kx : kx + kw]
    mask = feed.max(axis=2) > 60
    img[ky : ky + feed.shape[0], kx : kx + kw][mask] = feed[mask]
    return img
