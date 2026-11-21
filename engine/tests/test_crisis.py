"""One Berth from scripted calls. Run with: python -m pytest engine/tests -q"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from contracts.models import State
from engine.app import app
from engine.crisis import crisis_advise, start_crisis
from engine.core import new_game, step
from engine.game import GAME, Game
from engine.run_crisis import play
from contracts.models import Seat


def test_honest_both_dock_no_war():
    r = asyncio.run(play("honest", quiet=True))
    assert r["holders"] == {"ostrava": "berth", "zarnia": "berth"} and not r["war"]


def test_bluff_is_caught_and_ends_in_war():
    r = asyncio.run(play("bluff", quiet=True))
    assert r["decisions"]["ostrava"] == "blockade" and r["war"]
    assert r["trust"]["ostrava"] < 0.3


def test_interrupting_keeps_the_threat_private():
    r = asyncio.run(play("interrupt", quiet=True))
    assert r["decisions"]["ostrava"] != "blockade" and not r["war"]


def test_crisis_step_is_pure_and_every_tick_matches_the_contract():
    s = start_crisis(new_game(7, Seat(role="president", nation="valdoria")), "one_berth")
    while s.phase == "crisis":
        before = s.model_dump_json()
        nxt = step(s, [], 7)
        assert s.model_dump_json() == before
        assert step(s, [], 7).model_dump_json() == nxt.model_dump_json()
        State.model_validate(nxt.model_dump(mode="json", by_alias=True))
        s = nxt
    assert s.phase == "strategy" and s.crisis is None
    assert any(e.type == "crisis_resolved" for e in s.events)


def test_advice_ranks_crisis_actions_and_backdown_cost_applies():
    s = start_crisis(new_game(7, Seat(role="president", nation="valdoria")), "one_berth")
    types = {a.action.type for a in crisis_advise(s, "ostrava")}
    assert types == {"dock", "wait", "blockade"}
    from contracts.models import PublicCommitment
    s.crisis.public_commitments.append(PublicCommitment(nation="ostrava", action="blockade", tick=7))
    after = {a.action.type: a.score for a in crisis_advise(s, "ostrava")}
    assert crisis_advise(s, "ostrava")[0].action.type == "blockade" and after["wait"] < 0


def test_crisis_start_endpoint():
    GAME._decide_fn = None
    c = TestClient(app)
    c.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}})
    assert c.post("/crisis/start", json={"id": "nope"}).status_code == 404
    r = c.post("/crisis/start", json={"id": "one_berth"})
    assert r.status_code == 200 and r.json()["crisis"]["id"] == "one_berth"
    assert c.post("/crisis/start", json={"id": "one_berth"}).status_code == 409
    t = c.post("/turn").json()
    assert t["crisis"]["tick"] == 1 and t["incoming_call"]["from"] == "ostrava"
