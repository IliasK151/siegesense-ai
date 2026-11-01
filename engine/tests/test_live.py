import asyncio
import threading
import time

import cv2
import pytest
from hudsynth import render
from test_server import PROFILE, TOKEN, authed, recv_type, request

from siegesense_engine.capture.frames import FakeFrameSource
from siegesense_engine.game_watcher import FakeGameWatcher, GameState
from siegesense_engine.input.source import FakeInputSource
from siegesense_engine.profile import Profile
from siegesense_engine.server import EngineServer
from siegesense_engine.store import Store

SIZE = (1280, 720)
DIE = [("Bandit.X", "orange", "Ash.Main", "blue")]


class Match(threading.Thread):
    """Plays a scripted round as screen frames: alive → killed → round lost."""

    def __init__(self, source):
        super().__init__(daemon=True)
        self.source = source
        self.stop_flag = threading.Event()

    def run(self):
        t0 = time.perf_counter()
        while not self.stop_flag.is_set():
            e = time.perf_counter() - t0
            if e < 1.5:
                state = {"timer": int(90 - e), "score": (0, 0), "health": 100, "kills": []}
            elif e < 4.5:
                state = {"timer": int(90 - e), "score": (0, 0), "health": None, "kills": DIE}
            else:
                state = {"timer": None, "score": (0, 1), "health": None, "kills": []}
            self.source.push(render(state, size=SIZE))
            time.sleep(1 / 15)


async def make(tmp_path, frames, ocr, with_profile=True):
    store = Store(tmp_path / "s.db")
    if with_profile:
        store.save_profile(Profile.model_validate(PROFILE))
    server = EngineServer(
        token=TOKEN, store=store, watcher=FakeGameWatcher(GameState(True, True)),
        documents_dirs=[], status_interval=0.05, input_source=FakeInputSource(),
        frame_source=frames, ocr=ocr, clips_dir=tmp_path / "clips",
    )  # fmt: skip
    return server, await server.start(0), store


async def test_live_without_capture_errors(tmp_path, ocr):
    server, port, _ = await make(tmp_path, None, ocr)
    try:
        ws = await authed(port)
        res = await request(ws, "start_live")
        assert res["error"]["code"] == "capture_unavailable"
        await ws.close()
    finally:
        await server.stop()


async def test_live_requires_profile(tmp_path, ocr):
    server, port, _ = await make(tmp_path, FakeFrameSource(SIZE), ocr, with_profile=False)
    try:
        ws = await authed(port)
        assert (await request(ws, "start_live"))["error"]["code"] == "no_profile"
        await ws.close()
    finally:
        await server.stop()


@pytest.mark.ocr
async def test_live_pushes_round_and_death(tmp_path, ocr):
    frames = FakeFrameSource(SIZE)
    server, port, store = await make(tmp_path, frames, ocr)
    match = Match(frames)
    try:
        ws = await authed(port)
        assert (await request(ws, "start_live"))["ok"]
        match.start()
        seen = {}
        async with asyncio.timeout(20):
            while not {"death", "round_end"} <= seen.keys() or "summary" not in seen:
                msg = await recv_type_any(ws, {"live_event", "round_summary"})
                if msg["type"] == "round_summary":
                    seen["summary"] = msg["payload"]
                else:
                    seen[msg["payload"]["kind"]] = msg["payload"]
        death = seen["death"]
        assert death["confidence"] == "ok"
        assert death["data"]["killer"] == "Bandit.X"
        assert death["clip"].endswith(".mp4")
        assert (tmp_path / "clips" / death["clip"]).exists()
        assert seen["round_end"]["data"]["result"] == "loss"
        assert seen["summary"]["died"] and seen["summary"]["result"] == "loss"

        res = await request(ws, "stop_live", id="stop")
        summary = res["data"]
        assert summary["id"] == 1
        assert len(summary["rounds"]) == 1
        assert summary["deaths"][0]["clip"] == death["clip"]
        assert store.recent_matches()[0]["id"] == 1
        await ws.close()
    finally:
        match.stop_flag.set()
        await server.stop()


async def recv_type_any(ws, types):
    import json

    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
        if msg["type"] in types:
            return msg


@pytest.mark.ocr
async def test_hud_check_file(tmp_path, ocr):
    server, port, _ = await make(tmp_path, None, ocr)
    img = tmp_path / "shot.png"
    cv2.imwrite(str(img), render({"timer": 165, "score": (2, 1), "health": 87, "kills": DIE}))
    try:
        ws = await authed(port)
        res = await request(ws, "hud_check_file", {"path": str(img)})
        data = res["data"]
        assert data["image_jpeg_b64"]
        readers = {r["key"]: r for r in data["readers"]}
        assert readers["timer"]["ok"] and readers["health"]["text"] == "87"
        missing = await request(ws, "hud_check_file", {"path": str(tmp_path / "nope.png")}, id="m")
        assert missing["error"]["code"] == "not_found"
        await ws.close()
    finally:
        await server.stop()


async def test_capture_and_hud_lights(tmp_path, ocr):
    server, port, _ = await make(tmp_path, None, ocr)
    try:
        ws = await authed(port)
        status = await recv_type(ws, "status")
        lights = status["payload"]["lights"]
        assert lights["capture"]["state"] == "warn"
        assert lights["capture"]["fix"]
        assert lights["hud"]["state"] == "off"
        await ws.close()
    finally:
        await server.stop()


def test_live_fixtures_validate(protocol_fixtures):
    from siegesense_engine.hud.reader import HudCheckResult
    from siegesense_engine.live import LiveEventOut, MatchSummary
    from siegesense_engine.protocol import parse
    from siegesense_engine.rounds import RoundSummary

    def payload(name):
        return parse((protocol_fixtures / name).read_text()).payload

    assert LiveEventOut.model_validate(payload("live_event.json")).kind == "death"
    assert RoundSummary.model_validate(payload("round_summary.json")).died
    assert HudCheckResult.model_validate(payload("hud_check.json")["data"]).readers
    assert MatchSummary.model_validate(payload("match_summary.json")["data"]).rounds


@pytest.mark.ocr
async def test_hud_check_uses_draft_regions(tmp_path, ocr):
    server, port, _ = await make(tmp_path, None, ocr)
    img = tmp_path / "shot.png"
    cv2.imwrite(str(img), render({"timer": 165, "score": (2, 1), "health": 87, "kills": []}))
    shifted = {
        "killfeed": {"x": 0.7, "y": 0.08, "w": 0.29, "h": 0.22},
        "timer": {"x": 0.1, "y": 0.5, "w": 0.06, "h": 0.045},
        "score_left": {"x": 0.42, "y": 0.015, "w": 0.04, "h": 0.045},
        "score_right": {"x": 0.54, "y": 0.015, "w": 0.04, "h": 0.045},
        "health": {"x": 0.02, "y": 0.88, "w": 0.07, "h": 0.07},
        "centre": {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2},
    }
    try:
        ws = await authed(port)
        res = await request(ws, "hud_check_file", {"path": str(img), "regions": shifted})
        readers = {r["key"]: r for r in res["data"]["readers"]}
        assert not readers["timer"]["ok"]  # the draft box is off the timer
        assert res["data"]["regions"]["timer"]["x"] == 0.1
        bad = await request(
            ws, "hud_check_file", {"path": str(img), "regions": {"timer": 5}}, id="b"
        )
        assert bad["error"]["code"] == "invalid_regions"
        await ws.close()
    finally:
        await server.stop()
