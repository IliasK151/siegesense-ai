import asyncio
import base64
import json

import httpx
import pytest
from test_live import SIZE, Match, recv_type_any
from test_server import PROFILE, TOKEN, authed, recv_type, request
from test_stt import wav

from siegesense_engine.capture.frames import FakeFrameSource
from siegesense_engine.coach.stt import FakeStt
from siegesense_engine.game_watcher import FakeGameWatcher, GameState
from siegesense_engine.input.source import FakeInputSource
from siegesense_engine.profile import Profile
from siegesense_engine.server import EngineServer
from siegesense_engine.store import Store


def no_ollama():
    def refuse(request):
        raise httpx.ConnectError("refused")

    return httpx.MockTransport(refuse)


async def make(tmp_path, ocr, frames=None, coach=None, stt=None):
    store = Store(tmp_path / "s.db")
    store.save_profile(Profile.model_validate({**PROFILE, "coach": coach or {}}))
    server = EngineServer(
        token=TOKEN, store=store, watcher=FakeGameWatcher(GameState(True, True)),
        documents_dirs=[], status_interval=0.05, input_source=FakeInputSource(),
        frame_source=frames or FakeFrameSource(SIZE), ocr=ocr, clips_dir=tmp_path / "clips",
        stt=stt or FakeStt("why do I keep dying"), llm_transport=no_ollama(),
    )  # fmt: skip
    return server, await server.start(0)


async def play(ws, frames, until):
    match = Match(frames)
    match.start()
    got = []
    try:
        async with asyncio.timeout(25):
            while not until(got):
                got.append(await recv_type_any(ws, {"live_event", "tip", "round_summary"}))
    finally:
        match.stop_flag.set()
    return got


@pytest.mark.ocr
async def test_death_tip_pushed(tmp_path, ocr):
    frames = FakeFrameSource(SIZE)
    server, port = await make(tmp_path, ocr, frames)
    try:
        ws = await authed(port)
        await request(ws, "start_live")
        got = await play(ws, frames, lambda g: any(m["type"] == "tip" for m in g))
        tip = next(m for m in got if m["type"] == "tip")["payload"]
        death = next(
            m for m in got if m["type"] == "live_event" and m["payload"]["kind"] == "death"
        )
        assert got.index(death) < next(i for i, m in enumerate(got) if m["type"] == "tip")
        assert tip["slot"] == "death" and tip["rule"] in ("early_death", "first_death")
        assert tip["evidence"] and tip["round"] == 1
        await ws.close()
    finally:
        await server.stop()


@pytest.mark.ocr
async def test_death_then_round_end_single_tip(tmp_path, ocr):
    frames = FakeFrameSource(SIZE)
    server, port = await make(tmp_path, ocr, frames)
    try:
        ws = await authed(port)
        await request(ws, "start_live")
        got = await play(ws, frames, lambda g: any(m["type"] == "round_summary" for m in g))
        await asyncio.sleep(0.5)
        tips = [m for m in got if m["type"] == "tip"]
        assert len(tips) == 1
        await ws.close()
    finally:
        await server.stop()


@pytest.mark.ocr
async def test_frequency_report_only(tmp_path, ocr):
    frames = FakeFrameSource(SIZE)
    server, port = await make(tmp_path, ocr, frames, coach={"tip_frequency": "report_only"})
    try:
        ws = await authed(port)
        await request(ws, "start_live")
        got = await play(ws, frames, lambda g: any(m["type"] == "round_summary" for m in g))
        assert not [m for m in got if m["type"] == "tip"]
        res = await request(ws, "stop_live", id="stop")
        report = res["data"]["report"]
        assert report["drill"]["key"] and report["summary_line"]
        await ws.close()
    finally:
        await server.stop()


@pytest.mark.ocr
async def test_match_report_on_stop(tmp_path, ocr):
    frames = FakeFrameSource(SIZE)
    server, port = await make(tmp_path, ocr, frames)
    try:
        ws = await authed(port)
        await request(ws, "start_live")
        await play(ws, frames, lambda g: any(m["type"] == "round_summary" for m in g))
        res = await request(ws, "stop_live", id="stop")
        report = res["data"]["report"]
        assert report["problems"] and report["problems"][0]["rule"] in (
            "early_death",
            "first_death",
        )
        assert report["drill"]["key"] == "slow_opening"
        await ws.close()
    finally:
        await server.stop()


async def test_ask_text_keyword(tmp_path, ocr):
    server, port = await make(tmp_path, ocr)
    try:
        ws = await authed(port)
        res = await request(ws, "ask", {"text": "what's the score"})
        assert res["data"]["slot"] == "answer" and "0–0" in res["data"]["text"]
        await ws.close()
    finally:
        await server.stop()


async def test_ask_audio_with_fake_stt(tmp_path, ocr):
    server, port = await make(tmp_path, ocr)
    try:
        ws = await authed(port)
        res = await request(ws, "ask_audio", {"wav_b64": base64.b64encode(wav()).decode()})
        assert res["data"]["text"] == "why do I keep dying"
        assert res["data"]["tip"]["rule"] == "answer_deaths"
        bad = await request(ws, "ask_audio", {"wav_b64": "bm9wZQ=="}, id="b")
        assert bad["error"]["code"] == "bad_audio"
        await ws.close()
    finally:
        await server.stop()


async def test_ask_audio_stt_unavailable(tmp_path, ocr):
    server, port = await make(tmp_path, ocr, stt=FakeStt(state="unavailable"))
    try:
        ws = await authed(port)
        res = await request(ws, "ask_audio", {"wav_b64": base64.b64encode(wav()).decode()})
        assert res["error"]["code"] == "stt_unavailable"
        await ws.close()
    finally:
        await server.stop()


async def test_live_and_warmup_exclusive(tmp_path, ocr):
    server, port = await make(tmp_path, ocr)
    try:
        ws = await authed(port)
        assert (await request(ws, "start_warmup"))["ok"]
        res = await request(ws, "start_live", id="l")
        assert res["error"]["code"] == "busy"
        await request(ws, "stop_warmup", id="s")
        assert (await request(ws, "start_live", id="l2"))["ok"]
        res = await request(ws, "start_warmup", id="w")
        assert res["error"]["code"] == "busy"
        await ws.close()
    finally:
        await server.stop()


async def test_coach_and_voice_lights(tmp_path, ocr):
    server, port = await make(tmp_path, ocr, stt=FakeStt(state="not_downloaded"))
    try:
        ws = await authed(port)
        lights = (await recv_type(ws, "status"))["payload"]["lights"]
        assert lights["coach"]["state"] == "warn" and "Ollama" in lights["coach"]["fix"]
        assert (
            lights["voice"]["state"] == "warn" and "Download speech model" in lights["voice"]["fix"]
        )
        status = await request(ws, "coach_status")
        assert status["data"]["stt"] == "not_downloaded"
        assert status["data"]["llm"]["available"] is False
        await ws.close()
    finally:
        await server.stop()


def test_tip_fixture_validates(protocol_fixtures):
    from siegesense_engine.coach.brain import Tip
    from siegesense_engine.live import MatchSummary
    from siegesense_engine.protocol import parse

    tip = Tip.model_validate(parse((protocol_fixtures / "tip.json").read_text()).payload)
    assert tip.evidence
    data = json.loads((protocol_fixtures / "match_summary.json").read_text())["payload"]["data"]
    assert MatchSummary.model_validate(data).report.drill
