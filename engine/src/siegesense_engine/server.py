"""Authenticated localhost WebSocket server that the app talks to."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from . import __version__
from .game_watcher import GameWatcher
from .gamesettings import find_game_settings, parse_game_settings
from .profile import Profile
from .protocol import Envelope, ProtocolError, error_response, make, parse, response
from .status import StatusBoard
from .store import Store

log = logging.getLogger(__name__)

UNAUTHORIZED = 4401
HELLO_TIMEOUT = 5.0


class RequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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
    ) -> None:
        self._token = token
        self._store = store
        self._documents_dirs = documents_dirs
        self._status_interval = status_interval
        self._board = StatusBoard(watcher, store.get_profile)
        self._clients: set[ServerConnection] = set()
        self._last_status: str | None = None
        self._server: Server | None = None
        self._ticker: asyncio.Task | None = None
        self._handlers: dict[str, Handler] = {
            "get_profile": self._get_profile,
            "save_profile": self._save_profile,
            "find_game_settings": self._find_game_settings,
            "import_game_settings": self._import_game_settings,
            "get_status": self._get_status,
        }

    # -- lifecycle -------------------------------------------------------------------------
    async def start(self, port: int = 0) -> int:
        self._server = await serve(self._handle, "127.0.0.1", port)
        self._ticker = asyncio.create_task(self._status_loop())
        return self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
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
        if env is None or env.type != "hello" or env.payload.get("token") != self._token:
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
    async def _status_message(self) -> str:
        status = await asyncio.to_thread(self._board.compute)
        self._last_status = status.model_dump_json()
        return make("status", status)

    async def _status_loop(self) -> None:
        while True:
            await asyncio.sleep(self._status_interval)
            if not self._clients:
                continue
            previous = self._last_status
            message = await self._status_message()
            if self._last_status == previous:
                continue
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
        status = await asyncio.to_thread(self._board.compute)
        return status.model_dump(mode="json")
