"""Shared coach resources: the local AI (with a cached status), speech-to-text and answers."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import httpx

from .answers import Answerer, SessionFacts
from .brain import Tip
from .llm import LlmStatus, LocalLLM
from .settings import CoachSettings
from .stt import SpeechToText

log = logging.getLogger(__name__)
STATUS_TTL = 30.0


class CoachService:
    def __init__(
        self,
        stt: SpeechToText,
        llm_base_url: str = "http://127.0.0.1:11434",
        llm_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.stt = stt
        self._base = llm_base_url
        self._transport = llm_transport
        self._llm: LocalLLM | None = None
        self._llm_model: str | None = None
        self.llm_status: LlmStatus | None = None
        self._refreshing: asyncio.Task | None = None

    def llm(self, settings: CoachSettings) -> LocalLLM:
        if self._llm is None or self._llm_model != settings.llm_model:
            self._llm = LocalLLM(self._base, settings.llm_model, transport=self._transport)
            self._llm_model = settings.llm_model
        return self._llm

    async def refresh(self, settings: CoachSettings) -> LlmStatus:
        self.llm_status = await self.llm(settings).status()
        return self.llm_status

    async def refresh_loop(self, get_settings) -> None:
        while True:
            with contextlib.suppress(Exception):
                await self.refresh(await get_settings())
            await asyncio.sleep(STATUS_TTL)

    def _ai_ready(self, settings: CoachSettings) -> bool:
        return settings.llm_enabled and bool(self.llm_status and self.llm_status.available)

    async def say(self, tip: Tip, facts: dict[str, Any], settings: CoachSettings) -> Tip:
        """Rewrites a rule tip in natural words when the local AI is on and answers in time."""
        if not self._ai_ready(settings):
            return tip
        text = await self.llm(settings).rewrite(tip, facts)
        return tip.model_copy(update={"text": text})

    async def answer(self, question: str, facts: SessionFacts, settings: CoachSettings) -> Tip:
        llm = self.llm(settings) if self._ai_ready(settings) else None
        return await Answerer(llm).answer(question, facts)
