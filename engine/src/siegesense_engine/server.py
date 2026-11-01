"""Authenticated localhost WebSocket server that the app talks to."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from . import __version__
from .capture.frames import FrameSource, UnavailableFrameSource
from .capture.service import CaptureHub
from .errors import RequestError
from .game_watcher import GameWatcher
from .gamesettings import find_game_settings, parse_game_settings
from .input.hub import InputHub
from .input.source import InputSource, UnavailableInputSource
from .profile import Profile
from .protocol import (
    LIGHT_KEYS,
    Envelope,
    Light,
    ProtocolError,
    StatusPayload,
    error_response,
    make,
    parse,
    response,
)
from .services import CalibrationService, WarmupService
from .status import StatusBoard
from .store import Store

log = logging.getLogger(__name__)

UNAUTHORIZED = 4401
HELLO_TIMEOUT = 5.0


Handler = Callable[[dict[str, Any]], Awaitable[Any]]


def _validation_message(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err["loc"])
    return f"{where}: {err['msg']}" if where else err["msg"]


class EngineServer:
    def __init__(
        self,
        *,
        token: str,
        store: Store,
        watcher: GameWatcher,
        documents_dirs: list[Path],
        status_interval: float = 1.0,
        input_source: InputSource | None = None,
        metrics_interval: float = 0.5,
        frame_source: FrameSource | None = None,
    ) -> None:
        self._token = token
        self._store = store
        self._documents_dirs = documents_dirs
        self._status_interval = status_interval
        source = input_source or UnavailableInputSource("Input tracking works on Windows only")
        self._hub = InputHub(source)
        self._board = StatusBoard(
            watcher,
            store.get_profile,
            lambda: (
                source.available and self._hub.error is None,
                self._hub.error or source.reason,
                self._hub.active,
            ),
        )
        frames = frame_source or UnavailableFrameSource("Screen capture works on Windows only")
        self._capture = CaptureHub(frames)
        self.warmup = WarmupService(
            self._hub,
            store,
            self.broadcast,
            metrics_interval=metrics_interval,
            capture=self._capture,
        )
        self.calibration = CalibrationService(self._hub, self.broadcast)
        self._clients: set[ServerConnection] = set()
        self._server: Server | None = None
        self._ticker: asyncio.Task | None = None
        self._handlers: dict[str, Handler] = {
            "get_profile": self._get_profile,
            "save_profile": self._save_profile,
            "find_game_settings": self._find_game_settings,
            "import_game_settings": self._import_game_settings,
            "get_status": self._get_status,
            "start_warmup": self.warmup.start,
            "stop_warmup": self.warmup.stop,
            "get_warmup_history": self.warmup.history,
            "start_calibration": self.calibration.start,
            "cancel_calibration": self.calibration.cancel,
        }

    # -- lifecycle -------------------------------------------------------------------------
    async def start(self, port: int = 0) -> int:
        self._server = await serve(self._handle, "127.0.0.1", port)
        self._ticker = asyncio.create_task(self._status_loop())
        return self._server.sockets[0].getsockname()[1]

    async def broadcast(self, type: str, payload: BaseModel | dict) -> None:
        message = make(type, payload)
        for ws in list(self._clients):
            with contextlib.suppress(ConnectionClosed):
                await ws.send(message)

    async def stop(self) -> None:
        await self.warmup.shutdown()
        await self.calibration.cancel()
        if self._ticker:
            self._ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ticker
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    # -- connections -----------------------------------------------------------------------
    async def _handle(self, ws: ServerConnection) -> None:
        if not await self._authenticate(ws):
            return
        self._clients.add(ws)
        try:
            await ws.send(await self._status_message())
            async for raw in ws:
                await ws.send(await self._dispatch(raw))
        except ConnectionClosed:
            pass
        finally:
            self._clients.discard(ws)

    async def _authenticate(self, ws: ServerConnection) -> bool:
        try:
            env = parse(await asyncio.wait_for(ws.recv(), HELLO_TIMEOUT))
        except (TimeoutError, ProtocolError, ConnectionClosed):
            env = None
        token = str(env.payload.get("token", "")) if env is not None else ""
        if env is None or env.type != "hello" or not hmac.compare_digest(token, self._token):
            with contextlib.suppress(ConnectionClosed):
                await ws.close(UNAUTHORIZED, "unauthorized")
            return False
        await ws.send(response(env.id or "", {"engine_version": __version__}))
        return True

    async def _dispatch(self, raw: str | bytes) -> str:
        try:
            env: Envelope = parse(raw if isinstance(raw, str) else raw.decode())
        except (ProtocolError, UnicodeDecodeError) as exc:
            return error_response("", "bad_message", str(exc))
        rid = env.id or ""
        handler = self._handlers.get(env.type)
        if handler is None:
            return error_response(rid, "unknown_type", f"unknown message type: {env.type}")
        try:
            return response(rid, await handler(env.payload))
        except RequestError as exc:
            return error_response(rid, exc.code, exc.message)
        except Exception as exc:  # never let one bad request kill the connection
            log.exception("handler %s failed", env.type)
            return error_response(rid, "internal", str(exc))

    # -- status ----------------------------------------------------------------------------
    def _safe_compute(self) -> StatusPayload:
        """Never let a failing status check kill the ticker or a new connection."""
        try:
            return self._board.compute()
        except Exception as exc:
            log.exception("status check failed")
            lights = {
                key: Light(state="off", label=key.title(), detail="Status unavailable")
                for key in LIGHT_KEYS
            }
            lights["game"] = Light(
                state="error",
                label="Status check failed",
                detail=str(exc) or type(exc).__name__,
                fix="It will retry automatically. Restart SiegeSense if this stays red.",
            )
            return StatusPayload(lights=lights)

    async def _status_message(self) -> str:
        status = await asyncio.to_thread(self._safe_compute)
        return make("status", status)

    async def _status_loop(self) -> None:
        last_broadcast: str | None = None
        while True:
            await asyncio.sleep(self._status_interval)
            if not self._clients:
                continue
            status = await asyncio.to_thread(self._safe_compute)
            current = status.model_dump_json()
            if current == last_broadcast:
                continue
            last_broadcast = current
            message = make("status", status)
            for ws in list(self._clients):
                with contextlib.suppress(ConnectionClosed):
                    await ws.send(message)

    # -- handlers --------------------------------------------------------------------------
    async def _get_profile(self, _: dict[str, Any]) -> dict[str, Any]:
        profile = await asyncio.to_thread(self._store.get_profile)
        return {"profile": profile.model_dump(mode="json") if profile else None}

    async def _save_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            profile = Profile.model_validate(payload.get("profile"))
        except ValidationError as exc:
            raise RequestError("invalid_profile", _validation_message(exc)) from exc
        await asyncio.to_thread(self._store.save_profile, profile)
        return {"profile": profile.model_dump(mode="json")}

    async def _find_game_settings(self, _: dict[str, Any]) -> dict[str, Any]:
        return {"files": await asyncio.to_thread(find_game_settings, self._documents_dirs)}

    async def _import_game_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(payload.get("path", "")))
        if not path.is_file():
            raise RequestError("not_found", f"settings file not found: {path}")
        result = await asyncio.to_thread(parse_game_settings, path)
        return {"values": result.values, "missing": result.missing, "source": result.source}

    async def _get_status(self, _: dict[str, Any]) -> dict[str, Any]:
        status = await asyncio.to_thread(self._safe_compute)
        return status.model_dump(mode="json")
