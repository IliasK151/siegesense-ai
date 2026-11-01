import asyncio
import json

import httpx

from siegesense_engine.coach.brain import Tip
from siegesense_engine.coach.llm import LocalLLM, grounded, strip_thinking

TIP = Tip(rule="early_death", slot="death", round=2, text="You died 12 seconds into the round.",
          evidence={"time_alive_s": 12.0})  # fmt: skip
FACTS = {"round": 2, "time_alive_s": 12.0, "killer": "Bandit.X"}


def transport(models=("llama3.2:3b", "qwen3:4b"), reply="Slow down — you died 12 seconds in.",
              delay=0.0):  # fmt: skip
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in models]})
        if request.url.path == "/api/chat":
            seen["body"] = json.loads(request.content)
            if delay:
                await asyncio.sleep(delay)
            return httpx.Response(200, json={"message": {"role": "assistant", "content": reply}})
        return httpx.Response(404)

    return httpx.MockTransport(handler), seen


async def test_status_picks_preferred_model():
    t, _ = transport()
    s = await LocalLLM(transport=t).status()
    assert s.available and s.model == "qwen3:4b"
    assert s.models == ["llama3.2:3b", "qwen3:4b"]


async def test_status_uses_configured_model_if_installed():
    t, _ = transport()
    assert (await LocalLLM(model="llama3.2:3b", transport=t).status()).model == "llama3.2:3b"


async def test_status_unavailable():
    def boom(request):
        raise httpx.ConnectError("refused")

    s = await LocalLLM(transport=httpx.MockTransport(boom)).status()
    assert not s.available and s.model is None and "Ollama" in s.reason


async def test_status_no_models():
    t, _ = transport(models=())
    s = await LocalLLM(transport=t).status()
    assert not s.available and "ollama pull" in s.reason


async def test_rewrite_ok():
    t, seen = transport()
    text = await LocalLLM(transport=t).rewrite(TIP, FACTS)
    assert text == "Slow down — you died 12 seconds in."
    assert seen["body"]["model"] == "qwen3:4b" and seen["body"]["stream"] is False
    assert "12" in json.dumps(seen["body"]["messages"])


async def test_rewrite_timeout_falls_back():
    t, _ = transport(delay=0.3)
    llm = LocalLLM(transport=t, rewrite_timeout=0.1)
    assert await llm.rewrite(TIP, FACTS) == TIP.text


async def test_grounding_rejects_new_numbers():
    t, _ = transport(reply="You died 12 seconds in and lost 3 rounds.")
    assert await LocalLLM(transport=t).rewrite(TIP, FACTS) == TIP.text
    assert grounded("died 12 seconds in, round 2", FACTS, TIP.text)
    assert not grounded("died 13 seconds in", FACTS, TIP.text)
    assert grounded("12.0 seconds", FACTS, TIP.text)


async def test_strip_thinking():
    assert strip_thinking("<think>hmm 99</think>\n Slow down.") == "Slow down."
    t, _ = transport(reply="<think>count 77</think>Hold that angle — 12 seconds is too fast.")
    assert (
        await LocalLLM(transport=t).rewrite(TIP, FACTS)
        == "Hold that angle — 12 seconds is too fast."
    )


async def test_answer():
    t, _ = transport(reply="Bandit.X got you 12 seconds in. Drone first.")
    assert await LocalLLM(transport=t).answer("why did I die", FACTS) == (
        "Bandit.X got you 12 seconds in. Drone first."
    )
    t2, _ = transport(reply="You have 45 deaths.")
    assert await LocalLLM(transport=t2).answer("how many deaths", FACTS) is None
