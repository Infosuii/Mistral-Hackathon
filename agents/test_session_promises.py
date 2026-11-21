import asyncio

import pytest

from agents import fixtures, leaders
from engine.game import Game, advisers_choice


@pytest.mark.parametrize("recipient", ["ostrava", "zarnia"])
def test_kessaria_may_promise_specific_allocation(recipient):
    game = Game(use_agents=False)
    game.start_crisis("one_berth")
    action = f"assign_berth_{recipient}"
    view = fixtures.call_view("kessaria", f"I will pay for you to assign the berth to {recipient}.", s=game.state)
    state = game.state.model_dump()
    for phrase in (action, f"assign the berth to {recipient}"):
        result = leaders._parse_promises({"promises": [{"what": phrase}]}, view, state)
        assert [p["what"] for p in result] == [action]
    assert "berth" not in leaders._crisis_vocab(state, "kessaria")
    assert "berth" not in leaders._crisis_vocab(state, "nordhaven")


def test_same_seed_restart_discards_private_intents():
    observed = []
    async def decide(view):
        if view.nation == "ostrava":
            observed.append(list(view.earlier_private_intents))
        out = advisers_choice(view.state, view.nation, view.advice, "test")
        return out.model_copy(update={"private_intent": f"secure food for {view.nation}"})

    async def run():
        game = Game(seed=7, decide=decide, needle=False)
        await game.turn()
        await game.turn()
        game.reset(7)
        await game.turn()

    asyncio.run(run())
    assert observed == [[], ["month 0: secure food for ostrava"], []]


def test_wiretap_supplied_state_is_independent(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("offline")
    monkeypatch.setattr(leaders.llm, "hedged", unavailable)
    monkeypatch.setattr(leaders, "_game_context", lambda: pytest.fail("read the live session"))
    state = fixtures.state().model_dump()
    state["seat"] = {"role": "mediator", "nation": None}
    lines = asyncio.run(leaders.wiretap("ostrava", "zarnia", state))
    assert [line["speaker"] for line in lines] == ["ostrava", "zarnia"] * 2
    assert "neutral mediator" in lines[0]["text"]
