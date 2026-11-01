import asyncio
import json
import threading

import pytest

from siegesense_engine.input.events import Button, Key, MouseMove
from siegesense_engine.input.hub import InputHub
from siegesense_engine.input.source import (
    FakeInputSource,
    InputUnavailable,
    ReplayInputSource,
    UnavailableInputSource,
)


async def wait_for(cond, timeout=1.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not cond():
        if loop.time() > end:
            raise TimeoutError
        await asyncio.sleep(0.005)


async def test_hub_batches_in_order():
    source = FakeInputSource()
    hub = InputHub(source)
    got = []
    hub.subscribe(got.extend)
    await hub.acquire()
    events = [MouseMove(0.001 * i, i, 0) for i in range(5)]
    t = threading.Thread(target=lambda: source.emit(*events))
    t.start()
    t.join()
    await wait_for(lambda: len(got) == 5)
    assert got == events
    hub.release()


async def test_hub_refcount_starts_and_stops_source():
    source = FakeInputSource()
    hub = InputHub(source)
    await hub.acquire()
    await hub.acquire()
    assert source.started and hub.active
    hub.release()
    assert source.started
    hub.release()
    assert not source.started and not hub.active


async def test_unsubscribe_stops_delivery():
    source = FakeInputSource()
    hub = InputHub(source)
    got = []
    off = hub.subscribe(got.extend)
    await hub.acquire()
    off()
    source.emit(MouseMove(0.0, 1, 1))
    await asyncio.sleep(0.05)
    assert got == []
    hub.release()


async def test_unavailable_source():
    hub = InputHub(UnavailableInputSource("Input tracking works on Windows only"))
    with pytest.raises(InputUnavailable, match="Windows only"):
        await hub.acquire()
    assert not hub.active


async def test_replay_source_plays_file(tmp_path):
    f = tmp_path / "r.jsonl"
    lines = [
        {"k": "m", "t": 0.0, "dx": 5, "dy": -2},
        {"k": "b", "t": 0.1, "b": "left", "d": 1},
        {"k": "k", "t": 0.2, "vk": 0x77, "d": 0},
    ]
    f.write_text("\n".join(json.dumps(x) for x in lines))
    source = ReplayInputSource(f, speed=10)
    hub = InputHub(source)
    got = []
    hub.subscribe(got.extend)
    await hub.acquire()
    await wait_for(lambda: len(got) == 3)
    assert isinstance(got[0], MouseMove) and (got[0].dx, got[0].dy) == (5, -2)
    assert isinstance(got[1], Button) and got[1].button == "left" and got[1].down
    assert isinstance(got[2], Key) and got[2].vk == 0x77 and not got[2].down
    assert got[0].t < got[1].t < got[2].t
    hub.release()
