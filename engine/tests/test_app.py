"""The API and the turn loop's fallbacks. Run with: python -m pytest engine/tests -q"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contracts.models import Action, CallOutput, LeaderDetail, LeaderOutput, State
from engine import game as game_mod
from engine.app import app
from engine.game import GAME, Game

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"


@pytest.fixture
def client():
    GAME._decide_fn = None  # no model calls in tests
    with TestClient(app) as c:
        yield c


def test_start_state_turn_leaders(client):
    s = client.post("/start", json=json.loads((EXAMPLES / "start.request.json").read_text()))
    assert s.status_code == 200 and State.model_validate(s.json()).turn == 0
    for i in range(1, 4):
        r = client.post("/turn")
        assert r.status_code == 200 and r.json()["turn"] == i
    assert client.get("/state").json()["turn"] == 3
    assert client.get("/api/state").json()["turn"] == 3  # same routes under /api
    d = LeaderDetail.model_validate(client.get("/leaders/ostrava").json())
    assert d.advice and d.reason
    assert client.get("/leaders/atlantis").status_code == 404


def _run(g: Game) -> State:
    return asyncio.run(g.turn())


def test_slow_failing_and_illegal_leaders_fall_back(monkeypatch):
    monkeypatch.setattr(game_mod, "DECIDE_TIMEOUT_S", 0.2)

    async def decide(view):
        if view.nation == "ostrava":
            await asyncio.sleep(1)  # too slow
        if view.nation == "zarnia":
            raise RuntimeError("model down")
        if view.nation == "kessaria":  # illegal: war on itself
            return LeaderOutput(public_statement="Ha", private_intent="x", followed_advice=False, reason="r",
                                actions=[Action(type="declare_war", by="kessaria", target="kessaria")])
        return LeaderOutput(public_statement=f"{view.nation} speaks", private_intent="x", actions=[],
                            followed_advice=False, reason="r", messages=[{"to": "zarnia", "text": "hello"}])

    g = Game(seed=7, decide=decide)
    s = _run(g)
    assert s.turn == 1
    assert "Fell back" in g.leaders["ostrava"].reason and "Fell back" in g.leaders["zarnia"].reason
    assert g.leaders["kessaria"].chosen == [] or g.leaders["kessaria"].chosen[0].type != "declare_war"
    assert s.nations["nordhaven"].public_statement == "nordhaven speaks"
    assert g.inbox["zarnia"][0].from_ == "nordhaven"


def test_apply_call_updates_beliefs_relations_promises_and_queues_actions():
    g = Game(seed=7, use_agents=False)
    out = CallOutput.model_validate(json.loads((EXAMPLES / "call_reply.output.json").read_text()))
    out.actions = [Action(type="propose_trade", by="valdoria", target="ostrava",
                          params={"give": {"food": 10}, "get": {"oil": 10}})]
    before = g.state.model_copy(deep=True)
    s = g.apply_call("ostrava", out, interrupted=True, hesitation_ms=900)
    assert s.nations["ostrava"].beliefs.trust_in_player == pytest.approx(before.nations["ostrava"].beliefs.trust_in_player - 0.1)
    assert s.relations["ostrava|valdoria"] == before.relations["ostrava|valdoria"] - 5
    assert g.promises[0].to == "ostrava" and g.promises[0].by == "player"
    assert g.queued and before.model_dump_json() != s.model_dump_json()


def test_split_call_pending_then_filled():
    g = Game(seed=7, use_agents=False)
    cid = g.begin_call("ostrava")
    assert g.state.last_call.call_id == cid and g.state.last_call.pending
    out = CallOutput.model_validate(json.loads((EXAMPLES / "call_reply.output.json").read_text()))
    s = g.apply_call("ostrava", out, call_id=cid)
    assert s.last_call.call_id == cid and not s.last_call.pending
    assert s.last_call.promises[0].what == "berth"
    State.model_validate(s.model_dump(mode="json", by_alias=True))


def _reply(what="berth", to="ostrava"):
    return CallOutput(reply_text="ok", emotion="calm", belief_updates={"trust_in_player": 0, "resolve_of_player": 0},
                      promises=[{"to": to, "what": what, "when": "morning"}])


def test_late_reply_does_not_hide_a_newer_call():
    g = Game(seed=7, use_agents=False)
    g.start_crisis("one_berth")
    first = g.begin_call("ostrava")
    second = g.begin_call("zarnia")
    g.apply_call("ostrava", _reply(), call_id=first)  # the older call finishes last-but-one
    assert g.state.last_call.call_id == second and g.state.last_call.pending
    assert any(p.to == "ostrava" for p in g.state.crisis.promises)  # its promise still counts
    g.apply_call("zarnia", _reply(to="zarnia"), call_id=second)
    assert g.state.last_call.call_id == second and not g.state.last_call.pending


def test_reply_from_before_a_reset_is_dropped():
    g = Game(seed=7, use_agents=False)
    g.start_crisis("one_berth")
    old = g.begin_call("ostrava")
    g.reset(7)
    g.start_crisis("one_berth")
    g.apply_call("ostrava", _reply(), call_id=old)  # finishes after the reset
    assert g.state.crisis.promises == [] and g.state.last_call is None and not g.queued
