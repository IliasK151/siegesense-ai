import asyncio
import json

import pytest
from conftest import TEST_FIXTURES
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from siegesense_engine.game_watcher import FakeGameWatcher, GameState
from siegesense_engine.server import EngineServer
from siegesense_engine.store import Store

TOKEN = "secret-token"
PROFILE = {"in_game_name": "Ash.Main", "dpi": 800, "yaw_sensitivity": 10, "pitch_sensitivity": 10}


@pytest.fixture
async def engine(tmp_path):
    watcher = FakeGameWatcher(GameState(False, False))
    server = EngineServer(
        token=TOKEN,
        store=Store(tmp_path / "s.db"),
        watcher=watcher,
        documents_dirs=[tmp_path / "docs"],
        status_interval=0.05,
    )
    port = await server.start(0)
    yield server, port, watcher
    await server.stop()


async def send(ws, type, payload=None, id="1"):
    await ws.send(json.dumps({"type": type, "id": id, "ts": 0, "payload": payload or {}}))


async def recv_type(ws, type, timeout=2.0):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if msg["type"] == type:
            return msg


async def authed(port):
    ws = await connect(f"ws://127.0.0.1:{port}")
    await send(ws, "hello", {"token": TOKEN}, id="h")
    hello = await recv_type(ws, "response")
    assert hello["payload"]["ok"] is True
    return ws


async def request(ws, type, payload=None, id="r"):
    await send(ws, type, payload, id=id)
    msg = await recv_type(ws, "response")
    assert msg["id"] == id
    return msg["payload"]


async def test_rejects_wrong_token(engine):
    _, port, _ = engine
    async with connect(f"ws://127.0.0.1:{port}") as ws:
        await send(ws, "hello", {"token": "nope"})
        with pytest.raises(ConnectionClosed) as exc:
            await asyncio.wait_for(ws.recv(), 2)
        assert exc.value.rcvd.code == 4401


async def test_rejects_non_hello_first_message(engine):
    _, port, _ = engine
    async with connect(f"ws://127.0.0.1:{port}") as ws:
        await send(ws, "get_profile")
        with pytest.raises(ConnectionClosed) as exc:
            await asyncio.wait_for(ws.recv(), 2)
        assert exc.value.rcvd.code == 4401


async def test_hello_then_status_push(engine):
    _, port, _ = engine
    ws = await connect(f"ws://127.0.0.1:{port}")
    await send(ws, "hello", {"token": TOKEN}, id="h")
    hello = await recv_type(ws, "response")
    assert hello["payload"]["data"]["engine_version"]
    status = await recv_type(ws, "status")
    assert status["payload"]["lights"]["game"]["state"] == "warn"
    await ws.close()


async def test_save_and_get_profile(engine):
    _, port, _ = engine
    ws = await authed(port)
    assert (await request(ws, "get_profile"))["data"] == {"profile": None}
    saved = await request(ws, "save_profile", {"profile": PROFILE})
    assert saved["ok"] is True
    got = await request(ws, "get_profile")
    assert got["data"]["profile"]["in_game_name"] == "Ash.Main"
    assert got["data"]["profile"]["fov"] == 75.0
    await ws.close()


async def test_save_invalid_profile_errors(engine):
    _, port, _ = engine
    ws = await authed(port)
    bad = await request(ws, "save_profile", {"profile": {**PROFILE, "dpi": 0}})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "invalid_profile"
    assert "dpi" in bad["error"]["message"]
    assert (await request(ws, "get_profile", id="again"))["ok"] is True
    await ws.close()


async def test_import_game_settings(engine):
    _, port, _ = engine
    ws = await authed(port)
    path = str(TEST_FIXTURES / "GameSettings_utf8.ini")
    result = await request(ws, "import_game_settings", {"path": path})
    assert result["data"]["values"]["yaw_sensitivity"] == 12
    assert result["data"]["missing"] == []
    await ws.close()


async def test_import_missing_file_not_found(engine, tmp_path):
    _, port, _ = engine
    ws = await authed(port)
    result = await request(ws, "import_game_settings", {"path": str(tmp_path / "nope.ini")})
    assert result["ok"] is False
    assert result["error"]["code"] == "not_found"
    await ws.close()


async def test_find_game_settings(engine, tmp_path):
    _, port, _ = engine
    f = tmp_path / "docs" / "My Games" / "Rainbow Six - Siege" / "abc" / "GameSettings.ini"
    f.parent.mkdir(parents=True)
    f.write_text("MouseYawSensitivity=5")
    ws = await authed(port)
    result = await request(ws, "find_game_settings")
    assert [x["path"] for x in result["data"]["files"]] == [str(f)]
    await ws.close()


async def test_unknown_type_errors(engine):
    _, port, _ = engine
    ws = await authed(port)
    result = await request(ws, "launch_rockets")
    assert result["error"]["code"] == "unknown_type"
    await ws.close()


async def test_malformed_message_keeps_connection(engine):
    _, port, _ = engine
    ws = await authed(port)
    await ws.send("{not json")
    msg = await recv_type(ws, "response")
    assert msg["payload"]["error"]["code"] == "bad_message"
    assert (await request(ws, "get_status"))["data"]["lights"]["game"]
    await ws.close()


async def test_status_push_on_change(engine):
    _, port, watcher = engine
    ws = await authed(port)
    await recv_type(ws, "status")
    watcher.state = GameState(True, True)
    status = await recv_type(ws, "status")
    assert status["payload"]["lights"]["game"]["state"] == "ok"
    await ws.close()


class FlakyWatcher(FakeGameWatcher):
    """Raises on the polls listed in fail_on, otherwise returns state."""

    def __init__(self, fail_on: set[int]):
        super().__init__(GameState(False, False))
        self.calls = 0
        self.fail_on = fail_on

    def poll(self):
        self.calls += 1
        if self.calls in self.fail_on:
            raise RuntimeError("psutil exploded")
        return self.state


async def test_status_loop_survives_watcher_error(tmp_path):
    watcher = FlakyWatcher(fail_on={2, 3})
    server = EngineServer(
        token=TOKEN,
        store=Store(tmp_path / "s.db"),
        watcher=watcher,
        documents_dirs=[],
        status_interval=0.05,
    )
    port = await server.start(0)
    try:
        ws = await authed(port)
        await recv_type(ws, "status")
        watcher.state = GameState(True, True)
        seen = []
        while not seen or seen[-1] != "ok":
            status = await recv_type(ws, "status")
            seen.append(status["payload"]["lights"]["game"]["state"])
        assert "error" in seen  # the failure was shown, then the ticker recovered
        await ws.close()
    finally:
        await server.stop()


async def test_connect_survives_watcher_error(tmp_path):
    server = EngineServer(
        token=TOKEN,
        store=Store(tmp_path / "s.db"),
        watcher=FlakyWatcher(fail_on={1}),
        documents_dirs=[],
        status_interval=10,
    )
    port = await server.start(0)
    try:
        ws = await authed(port)
        assert (await request(ws, "get_profile"))["ok"] is True
        await ws.close()
    finally:
        await server.stop()
