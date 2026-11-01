import asyncio
import json
import subprocess
import sys
import time

import pytest
from synth import end_time, flick, to_counts
from test_server import PROFILE, TOKEN, authed, recv_type, request
from websockets.asyncio.client import connect

from siegesense_engine.game_watcher import FakeGameWatcher, GameState
from siegesense_engine.input.events import VK, Button, Key, MouseMove
from siegesense_engine.input.source import FakeInputSource, UnavailableInputSource
from siegesense_engine.mechanics.sensitivity import conversion
from siegesense_engine.profile import Profile
from siegesense_engine.server import EngineServer
from siegesense_engine.store import Store


async def make_server(tmp_path, source, with_profile=True):
    store = Store(tmp_path / "s.db")
    if with_profile:
        store.save_profile(Profile.model_validate(PROFILE))
    server = EngineServer(
        token=TOKEN,
        store=store,
        watcher=FakeGameWatcher(GameState(False, False)),
        documents_dirs=[],
        status_interval=0.05,
        input_source=source,
        metrics_interval=0.05,
    )
    return server, await server.start(0), store


@pytest.fixture
async def fake(tmp_path):
    source = FakeInputSource()
    server, port, store = await make_server(tmp_path, source)
    yield source, port, store
    await server.stop()


async def test_start_warmup_requires_profile(tmp_path):
    server, port, _ = await make_server(tmp_path, FakeInputSource(), with_profile=False)
    try:
        ws = await authed(port)
        res = await request(ws, "start_warmup")
        assert res["ok"] is False and res["error"]["code"] == "no_profile"
        await ws.close()
    finally:
        await server.stop()


async def test_start_warmup_without_input_errors(tmp_path):
    server, port, _ = await make_server(tmp_path, UnavailableInputSource("Windows only, sorry"))
    try:
        ws = await authed(port)
        res = await request(ws, "start_warmup")
        assert res["error"] == {"code": "input_unavailable", "message": "Windows only, sorry"}
        await ws.close()
    finally:
        await server.stop()


def flick_events(t0: float, overshoot: float = 0):
    conv = conversion(Profile.model_validate(PROFILE))
    samples = flick(t0, 30, 0.12, overshoot=overshoot)
    shot = end_time(samples) + 0.1
    return to_counts(samples, conv.yaw) + [
        Button(shot, "left", True),
        Button(shot + 0.05, "left", False),
    ]


async def test_warmup_pushes_flick_and_metrics(fake):
    source, port, _ = fake
    ws = await authed(port)
    res = await request(ws, "start_warmup")
    assert res["ok"] and res["data"]["conversion"] == "estimated"
    source.emit(*flick_events(time.perf_counter(), overshoot=6))
    f = await recv_type(ws, "flick", timeout=3)
    assert f["payload"]["id"] == 1 and f["payload"]["corrected"] is True
    m = await recv_type(ws, "metrics", timeout=2)
    assert m["payload"]["flicks"] >= 1
    await ws.close()


async def test_stop_returns_summary_and_persists(fake):
    source, port, store = fake
    ws = await authed(port)
    await request(ws, "start_warmup")
    source.emit(*flick_events(time.perf_counter()))
    await recv_type(ws, "flick", timeout=3)
    res = await request(ws, "stop_warmup", id="stop")
    summary = res["data"]
    assert summary["id"] == 1
    assert summary["metrics"]["flicks"] == 1
    assert summary["drill"] is None
    assert summary["history"][-1]["started_at"] == summary["started_at"]
    assert len(store.recent_warmups()) == 1
    hist = await request(ws, "get_warmup_history", id="h")
    assert len(hist["data"]["history"]) == 1
    await ws.close()


async def test_double_start_errors(fake):
    _, port, _ = fake
    ws = await authed(port)
    await request(ws, "start_warmup")
    res = await request(ws, "start_warmup", id="again")
    assert res["error"]["code"] == "already_running"
    res = await request(ws, "stop_warmup", id="s")
    assert res["ok"]
    res = await request(ws, "stop_warmup", id="s2")
    assert res["error"]["code"] == "not_running"
    await ws.close()


async def test_calibration_flow_over_ws(fake):
    source, port, _ = fake
    ws = await authed(port)
    res = await request(ws, "start_calibration")
    assert res["data"]["phase"] == "armed"
    t = time.perf_counter()
    for i, counts in enumerate([31400, 31600, 31500]):
        t0 = t + i
        source.emit(Key(t0, VK.F8, True), Key(t0 + 0.01, VK.F8, False))
        source.emit(*[MouseMove(t0 + 0.02 + k * 0.001, 100, 0) for k in range(counts // 100)])
        source.emit(Key(t0 + 0.5, VK.F8, True), Key(t0 + 0.51, VK.F8, False))
    while True:
        msg = await recv_type(ws, "calibration", timeout=3)
        if msg["payload"]["phase"] == "done":
            break
    assert msg["payload"]["result"] == 31500
    await asyncio.sleep(0.1)
    assert source.started is False  # input released once done
    await ws.close()


async def test_cancel_calibration(fake):
    source, port, _ = fake
    ws = await authed(port)
    await request(ws, "start_calibration")
    res = await request(ws, "cancel_calibration", id="c")
    assert res["data"]["phase"] == "cancelled"
    assert source.started is False
    await ws.close()


async def test_input_light_tracks_activity(fake):
    _, port, _ = fake
    ws = await authed(port)
    first = await recv_type(ws, "status")
    assert first["payload"]["lights"]["input"]["label"] == "Input ready"
    await request(ws, "start_warmup")
    while True:
        s = await recv_type(ws, "status", timeout=2)
        if s["payload"]["lights"]["input"]["label"] == "Tracking your mouse":
            break
    await ws.close()


def test_cli_replay_flag(tmp_path):
    replay = tmp_path / "r.jsonl"
    replay.write_text(json.dumps({"k": "m", "t": 0, "dx": 1, "dy": 0}) + "\n")
    proc = subprocess.Popen(
        [sys.executable, "-m", "siegesense_engine", "--token", "t", "--data-dir", str(tmp_path),
         "--replay-input", str(replay)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )  # fmt: skip
    try:
        assert proc.stdout.readline().startswith("READY ")
    finally:
        proc.stdin.close()
        assert proc.wait(timeout=5) == 0


async def test_unavailable_light_explains(tmp_path):
    server, port, _ = await make_server(tmp_path, UnavailableInputSource("Works on Windows only"))
    try:
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"type": "hello", "id": "h", "ts": 0,
                                      "payload": {"token": TOKEN}}))  # fmt: skip
            status = await recv_type(ws, "status")
            light = status["payload"]["lights"]["input"]
            assert light["state"] == "warn"
            assert light["detail"] == "Works on Windows only"
            assert light["fix"]
    finally:
        await server.stop()
