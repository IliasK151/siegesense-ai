import httpx
import pytest

from siegesense_engine.coach.answers import Answerer, SessionFacts
from siegesense_engine.coach.llm import LocalLLM

FACTS = SessionFacts(
    rounds_played=6, rounds_won=2, rounds_lost=4, deaths=5, first_deaths=3, untraded_deaths=4,
    avg_time_alive_s=31.5, last_death_round=6, last_death_killer="Bandit.X",
    last_death_time_alive_s=12.0, kills=4, repeeks=2, flicks=40, overshoot_pct=35,
    moving_shot_pct=22, recent_tips=["You took the first death."],
)  # fmt: skip


@pytest.mark.parametrize(
    "question,expect",
    [
        ("why is my aim bad", "35%"),
        ("why do I keep dying", "3 of your 5 deaths"),
        ("am I getting traded", "4 of your 5 deaths"),
        ("do I re-peek too much", "2 times"),
        ("what's the score", "2–4"),
        ("what's for dinner", "I can answer about"),
    ],
)
async def test_keyword_answers(question, expect):
    tip = await Answerer(None).answer(question, FACTS)
    assert tip.slot == "answer" and expect in tip.text
    assert tip.evidence


def _llm(reply):
    async def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
        return httpx.Response(200, json={"message": {"content": reply}})

    return LocalLLM(transport=httpx.MockTransport(handler))


async def test_llm_answer_used_when_grounded():
    tip = await Answerer(_llm("You died first 3 times. Let a teammate entry.")).answer(
        "dying?", FACTS
    )
    assert tip.text == "You died first 3 times. Let a teammate entry."
    assert tip.rule == "ai_answer"


async def test_llm_answer_ungrounded_falls_back():
    tip = await Answerer(_llm("You died 99 times.")).answer("why do I keep dying", FACTS)
    assert "3 of your 5 deaths" in tip.text and tip.rule == "answer_deaths"
