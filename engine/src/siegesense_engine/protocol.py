"""Wire protocol shared by the engine and the app.

Every message is a JSON envelope: ``{"type", "ts", "id"?, "payload"}``.
The sample messages in ``protocol/fixtures`` are the contract both sides test against.
"""

from __future__ import annotations

import json
import time
from typing import Any, Literal

from pydantic import BaseModel, ValidationError


class ProtocolError(ValueError):
    """Raised when an incoming message is not a valid envelope."""


class Envelope(BaseModel):
    type: str
    ts: int
    id: str | None = None
    payload: dict[str, Any] = {}


LightState = Literal["ok", "warn", "error", "off"]
LightKey = Literal["game", "capture", "input", "hud", "coach", "voice"]
LIGHT_KEYS: tuple[LightKey, ...] = ("game", "capture", "input", "hud", "coach", "voice")


class Light(BaseModel):
    state: LightState
    label: str
    detail: str
    fix: str | None = None


class StatusPayload(BaseModel):
    lights: dict[LightKey, Light]


class ErrorInfo(BaseModel):
    code: str
    message: str


def now_ms() -> int:
    return time.monotonic_ns() // 1_000_000


def _dump(payload: dict | BaseModel | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    return payload


def make(type: str, payload: dict | BaseModel | None = None, id: str | None = None) -> str:
    env: dict[str, Any] = {"type": type, "ts": now_ms(), "payload": _dump(payload)}
    if id is not None:
        env["id"] = id
    return json.dumps(env)


def response(id: str, payload: dict | BaseModel | None = None) -> str:
    return make("response", {"ok": True, "data": _dump(payload)}, id=id)


def error_response(id: str, code: str, message: str) -> str:
    return make("response", {"ok": False, "error": {"code": code, "message": message}}, id=id)


def parse(text: str) -> Envelope:
    try:
        raw = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProtocolError("message must be a JSON object")
    try:
        return Envelope.model_validate(raw, strict=False)
    except ValidationError as exc:
        raise ProtocolError(f"invalid envelope: {exc.errors()[0]['msg']}") from exc
