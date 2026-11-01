"""Optional local AI coach through Ollama (spec §4.9). Free and offline once a model is pulled.

The model only rephrases rule-based tips and answers questions from the session's facts. Any
answer that mentions a number not present in those facts is thrown away (grounding), and every
call has a short timeout so the player is never kept waiting.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
from pydantic import BaseModel

from .brain import Tip

PREFERRED = ("qwen3:4b", "llama3.2:3b", "phi4-mini", "gemma3:4b")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
THINK = re.compile(r"<think>.*?</think>", re.DOTALL)

SYSTEM = (
    "You are a calm, direct Rainbow Six Siege coach talking to the player between rounds. "
    "Speak in second person, at most 2 short sentences. Use ONLY the facts given; never invent "
    "numbers, names or events. Never mention enemy positions. No preamble."
)


class LlmStatus(BaseModel):
    available: bool
    model: str | None
    models: list[str] = []
    reason: str | None = None


def strip_thinking(text: str) -> str:
    return THINK.sub("", text).strip()


def _numbers(text: str) -> set[float]:
    return {float(n) for n in NUMBER.findall(text)}


def grounded(text: str, facts: dict[str, Any], base_text: str) -> bool:
    allowed = _numbers(json.dumps(facts)) | _numbers(base_text)
    return _numbers(text) <= allowed


def _pick_model(installed: list[str], wanted: str | None) -> str | None:
    if wanted and wanted in installed:
        return wanted
    for name in PREFERRED:
        if name in installed:
            return name
    return installed[0] if installed else None


class LocalLLM:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        rewrite_timeout: float = 4.0,
        answer_timeout: float = 10.0,
    ) -> None:
        self._base = base_url
        self._wanted = model
        self._transport = transport
        self._rewrite_timeout = rewrite_timeout
        self._answer_timeout = answer_timeout
        self._model: str | None = None

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=timeout, transport=self._transport)

    async def status(self) -> LlmStatus:
        try:
            async with self._client(1.5) as client:
                r = await client.get("/api/tags")
                r.raise_for_status()
                installed = [m["name"] for m in r.json().get("models", [])]
        except (httpx.HTTPError, ValueError, KeyError):
            self._model = None
            return LlmStatus(
                available=False, model=None, reason="Ollama is not running or not installed."
            )
        model = _pick_model(installed, self._wanted)
        self._model = model
        if model is None:
            return LlmStatus(
                available=False,
                model=None,
                models=installed,
                reason="No model installed. Run: ollama pull qwen3:4b",
            )
        return LlmStatus(available=True, model=model, models=installed)

    async def _chat(self, user: str, timeout: float) -> str | None:
        if self._model is None and not (await self.status()).available:
            return None
        body = {
            "model": self._model,
            "stream": False,
            "options": {"temperature": 0.4},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        }
        try:
            async with self._client(timeout) as client:
                r = await client.post("/api/chat", json=body)
                r.raise_for_status()
                content = r.json()["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None
        text = strip_thinking(str(content))
        return text or None

    async def rewrite(self, tip: Tip, facts: dict[str, Any]) -> str:
        """Natural wording for a rule tip; the original text if anything goes wrong."""
        prompt = (
            f"Facts: {json.dumps(facts)}\n"
            f"Coaching point: {tip.text}\n"
            "Say this coaching point to the player in your own words."
        )
        try:
            text = await asyncio.wait_for(
                self._chat(prompt, self._rewrite_timeout), self._rewrite_timeout
            )
        except TimeoutError:
            return tip.text
        if not text or not grounded(text, facts, tip.text):
            return tip.text
        return text

    async def answer(self, question: str, facts: dict[str, Any]) -> str | None:
        prompt = f"Facts about this match: {json.dumps(facts)}\nPlayer asks: {question}"
        try:
            text = await asyncio.wait_for(
                self._chat(prompt, self._answer_timeout), self._answer_timeout
            )
        except TimeoutError:
            return None
        if not text or not grounded(text, facts, question):
            return None
        return text
