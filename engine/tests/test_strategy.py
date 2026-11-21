"""Private strategy (DECIDED 13:07): written in the background, passed into LeaderView."""

from __future__ import annotations

import asyncio

from contracts.models import LeaderOutput
from engine import game as game_mod
from engine.game import Game


def _game(fake_strategize, seen):
    async def decide(view):
        seen.append((view.nation, view.private_strategy))
        return LeaderOutput(public_statement="", private_intent="", actions=[], followed_advice=True, reason="ok")
    g = Game.__new__(Game)  # build without running reset() outside a loop
    g._decide_fn, g.needle, g.lock = decide, False, asyncio.Lock()
    g._strategize_fn = lambda: fake_strategize
    return g


def test_strategy_reaches_decide_and_leaders_and_crisis_overrides():
    seen = []

    async def strategize_all(state):
        tag = state.crisis.id if state.crisis else "game"
        return {n: f"{tag} plan for {n}" for n in ("ostrava", "zarnia", "kessaria", "nordhaven")}

    async def go():
        g = _game(strategize_all, seen)
        g.reset(7)
        await g._strategy_task
        await g.turn()
        game_view = dict(seen)
        assert g.leader("ostrava").private_strategy == "game plan for ostrava"
        g.start_crisis("one_berth")
        await g._strategy_task
        assert g.leader("ostrava").private_strategy == "one_berth plan for ostrava"
        return game_view
    views = asyncio.run(go())
    assert views["ostrava"] == "game plan for ostrava" and "valdoria" not in views


def test_stale_strategy_after_reset_is_dropped():
    async def slow(state):
        await asyncio.sleep(0.05)
        return {"ostrava": "old plan"}

    async def go():
        g = _game(slow, [])
        g.reset(7)
        task = g._strategy_task
        g._strategize_fn = lambda: None
        g.reset(7)  # restart before the old strategies arrive
        await task
        return g.leader("ostrava").private_strategy
    assert asyncio.run(go()) is None


def test_flag_off_means_no_strategy(monkeypatch):
    monkeypatch.setattr(game_mod, "PRIVATE_STRATEGY", False)
    assert game_mod._load_strategize() is None
    g = Game(seed=7, use_agents=False, needle=False)
    assert g.leader("ostrava").private_strategy is None
