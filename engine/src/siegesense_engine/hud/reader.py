"""Combines the individual HUD readers into one reading per frame."""

from __future__ import annotations

import base64
from typing import Literal

import cv2
from pydantic import BaseModel

from ..capture.frames import Frame
from .digits import parse_timer, read_health, read_score, read_timer
from .killfeed import KillEntry, KillFeedReader, Team
from .ocr import OcrEngine, prep_text
from .regions import HudRegions, crop

LOW_CONF_AFTER = 10  # consecutive reads with no timer and no score
SNAPSHOT_WIDTH = 960


class KillEntryModel(BaseModel):
    killer: str
    victim: str
    killer_team: Team
    victim_team: Team
    killer_is_me: bool
    victim_is_me: bool
    headshot: bool | None
    confidence: float


class HudReading(BaseModel):
    t: float
    timer: int | None
    timer_conf: float
    score_mine: int | None
    score_theirs: int | None
    health: int | None
    health_conf: float
    kills: list[KillEntryModel]
    confidence: Literal["ok", "low"]


class ReaderResult(BaseModel):
    key: str
    text: str
    confidence: float
    ok: bool


class HudCheckResult(BaseModel):
    image_jpeg_b64: str
    width: int
    height: int
    regions: HudRegions
    readers: list[ReaderResult]


class HudReader:
    def __init__(
        self,
        ocr: OcrEngine,
        regions: HudRegions,
        own_name: str,
        my_score_side: Literal["left", "right"],
    ) -> None:
        self._ocr = ocr
        self.regions = regions
        self._side = my_score_side
        self._killfeed = KillFeedReader(ocr, own_name)
        self._calls = 0
        self._misses = 0
        self._scores: tuple[int | None, int | None] = (None, None)

    def _model(self, e: KillEntry) -> KillEntryModel:
        return KillEntryModel(
            killer=e.killer,
            victim=e.victim,
            killer_team=e.killer_team,
            victim_team=e.victim_team,
            killer_is_me=self._killfeed.is_me(e.killer),
            victim_is_me=self._killfeed.is_me(e.victim),
            headshot=e.headshot,
            confidence=e.confidence,
        )

    def _read_scores(self, image) -> tuple[int | None, int | None]:
        left = read_score(crop(image, self.regions.score_left), self._ocr).value
        right = read_score(crop(image, self.regions.score_right), self._ocr).value
        return (left, right) if self._side == "left" else (right, left)

    def read(self, frame: Frame) -> HudReading:
        image = frame.image
        timer = read_timer(crop(image, self.regions.timer), self._ocr)
        if self._calls % 2 == 0:
            self._scores = self._read_scores(image)
        self._calls += 1
        health = read_health(crop(image, self.regions.health), self._ocr)
        kills = self._killfeed.read(crop(image, self.regions.killfeed), frame.t)

        if timer.value is None and self._scores == (None, None):
            self._misses += 1
        else:
            self._misses = 0
        return HudReading(
            t=frame.t,
            timer=timer.value,
            timer_conf=timer.confidence,
            score_mine=self._scores[0],
            score_theirs=self._scores[1],
            health=health.value,
            health_conf=health.confidence,
            kills=[self._model(k) for k in kills],
            confidence="low" if self._misses >= LOW_CONF_AFTER else "ok",
        )

    def snapshot(self, frame: Frame) -> HudCheckResult:
        """One frame plus what every reader sees in it, for the HUD check screen."""
        image = frame.image
        h, w = image.shape[:2]
        small = cv2.resize(image, (SNAPSHOT_WIDTH, round(h * SNAPSHOT_WIDTH / w)), cv2.INTER_AREA)
        ok, jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        readers: list[ReaderResult] = []

        def raw(key: str, box, parsed_ok) -> None:
            text, conf = self._ocr.recognize(prep_text(crop(image, box)))
            readers.append(ReaderResult(key=key, text=text, confidence=conf, ok=parsed_ok(text)))

        raw("timer", self.regions.timer, lambda t: parse_timer(t) is not None)
        raw("score_left", self.regions.score_left, lambda t: t.strip().isdigit())
        raw("score_right", self.regions.score_right, lambda t: t.strip().isdigit())
        raw("health", self.regions.health, lambda t: t.strip().isdigit())
        fresh = KillFeedReader(self._ocr, self._killfeed._own)
        entries = fresh.read(crop(image, self.regions.killfeed), frame.t)
        readers.append(
            ReaderResult(
                key="killfeed",
                text="; ".join(f"{e.killer} → {e.victim}" for e in entries),
                confidence=min((e.confidence for e in entries), default=0.0),
                ok=bool(entries),
            )
        )
        return HudCheckResult(
            image_jpeg_b64=base64.b64encode(jpeg.tobytes()).decode() if ok else "",
            width=small.shape[1],
            height=small.shape[0],
            regions=self.regions,
            readers=readers,
        )
