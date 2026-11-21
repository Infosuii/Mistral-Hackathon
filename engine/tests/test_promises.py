"""Free-text promises from interpret() still count (Ashish's live One Berth test)."""

from __future__ import annotations

import asyncio

import pytest

from contracts.models import CallOutput, Seat
from engine.calls import normalise_promise
from engine.core import new_game
from engine.crisis import start_crisis
from engine.game import Game

S = start_crisis(new_game(7, Seat(role="president", nation="valdoria")), "one_berth")


@pytest.mark.parametrize("to,what,when,expect", [
    ("ostrava", "berth for full day", "now", ("berth", "all_day")),
    ("ostrava", "berth in the morning", "now", ("berth", "morning")),
    ("zarnia", "the berth", "tonight", ("berth", "evening")),
    ("ostrava", "berth", "all_day", ("berth", "all_day")),
    ("nordhaven", "send tugs to open a second berth", "now", ("send_tugs", "now")),
    ("ostrava", "grain from our reserves", "next month", ("grain from our reserves", "next month")),
])
def test_normalise(to, what, when, expect):
    assert normalise_promise(S, to, what, when) == expect


def _say(to, what, when):
    return CallOutput(reply_text="...", emotion="calm", belief_updates={"trust_in_player": 0, "resolve_of_player": 0},
                      promises=[{"to": to, "what": what, "when": when}])


def test_free_text_double_promise_is_caught_at_compare_notes():
    async def go():
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("one_berth")
        while g.state.phase == "crisis":
            s = await g.turn()
            if s.crisis and s.crisis.tick == 1:
                g.apply_call("ostrava", _say("ostrava", "I promise you the berth for the whole day", "now"))
            if s.crisis and s.crisis.tick == 3:
                g.apply_call("zarnia", _say("zarnia", "berth for full day", "now"))
        return [n.text for n in g.state.news]
    news = asyncio.run(go())
    assert any("promised the berth to both" in t for t in news)


def test_free_text_split_day_is_not_a_contradiction():
    async def go():
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("one_berth")
        while g.state.phase == "crisis":
            s = await g.turn()
            if s.crisis and s.crisis.tick == 1:
                g.apply_call("ostrava", _say("ostrava", "berth in the morning", "now"))
                g.apply_call("zarnia", _say("zarnia", "berth at night", "now"))
        return [n.text for n in g.state.news]
    news = asyncio.run(go())
    assert any("your story holds" in t for t in news)
