"""The needle. Run with: python -m pytest engine/tests -q"""

from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

from contracts.models import CallOutput, CrisisPromise, FuturesResponse, Seat
from engine.app import app
from engine.core import new_game
from engine.crisis import start_crisis
from engine.futures import futures, war_p
from engine.game import GAME, Game
from engine.snapshots import snapshot

SEAT = Seat(role="president", nation="valdoria")


def test_same_state_same_odds_and_repeatable():
    s = start_crisis(new_game(7, SEAT), "one_berth")
    r = futures(s, s, count=40)
    assert r.before.war_p == r.after.war_p
    assert futures(s, s, count=40).model_dump() == r.model_dump()


def test_honest_deal_lowers_war_odds_in_one_berth():
    s = start_crisis(new_game(7, SEAT), "one_berth")
    deal = s.model_copy(deep=True)
    deal.crisis.promises += [
        CrisisPromise(id="p1", tick=0, by="player", to="ostrava", what="berth", when="morning"),
        CrisisPromise(id="p2", tick=0, by="player", to="zarnia", what="berth", when="afternoon"),
    ]
    from contracts.models import Action
    r = futures(s, deal, first_after=[Action(type="send_tugs", by="nordhaven")], count=60)
    assert r.after.war_p < r.before.war_p, r
    assert "cuts" in r.caption


def test_full_needle_is_fast_enough():
    s = start_crisis(new_game(11, SEAT), "one_berth")
    t = time.time()
    futures(s, s.model_copy(update={"seed": 12}))
    assert time.time() - t < 5


def test_futures_endpoint_and_needle_after_a_call():
    GAME._decide_fn = None
    c = TestClient(app)
    c.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}})
    sid = snapshot(GAME.state)
    r = c.post("/futures", json={"snapshot_id": sid})
    assert r.status_code == 200 and FuturesResponse.model_validate(r.json())
    assert c.get("/state").json()["last_futures"] == r.json()
    assert c.post("/futures", json={"snapshot_id": "s_nope"}).status_code == 404


def test_needle_updates_state_after_a_call_in_the_server():
    async def go():
        g = Game(seed=7, use_agents=False)
        g.start_crisis("one_berth")
        out = CallOutput(reply_text="ok", emotion="calm", belief_updates={"trust_in_player": 0, "resolve_of_player": 0},
                         promises=[{"to": "ostrava", "what": "berth", "when": "morning"}])
        g.apply_call("ostrava", out)
        await g._needle_task
        return g.state.last_futures
    assert asyncio.run(go()) is not None


def test_stale_needle_results_are_dropped():
    async def go():
        g = Game(seed=7, use_agents=False)
        g.start_crisis("one_berth")
        out = CallOutput(reply_text="ok", emotion="calm", belief_updates={"trust_in_player": 0, "resolve_of_player": 0},
                         promises=[{"to": "ostrava", "what": "berth", "when": "morning"}])
        g.apply_call("ostrava", out)
        task = g._needle_task
        g.reset(7)  # the game restarts while the rollouts run
        await task
        return g.state.last_futures
    assert asyncio.run(go()) is None
