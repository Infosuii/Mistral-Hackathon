"""Mediator seat (DECIDED 13:09), behind GAMBIT_MEDIATOR."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from contracts.models import CallOutput, LeaderOutput, Seat, State
from engine import game as game_mod
from engine.app import app
from engine.game import GAME, Game

MEDIATOR = {"role": "mediator", "nation": None}


def test_seat_rules():
    Seat(role="mediator", nation=None)
    with pytest.raises(ValidationError):
        Seat(role="mediator", nation="valdoria")
    with pytest.raises(ValidationError):
        Seat(role="president", nation=None)


def test_mediator_is_off_by_default():
    GAME._decide_fn = None
    c = TestClient(app)
    assert c.post("/start", json={"seed": 7, "seat": MEDIATOR}).status_code == 400
    r = c.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}).json()
    assert r["available_roles"] is None


def test_mediator_game_all_five_act_and_score(monkeypatch):
    monkeypatch.setattr(game_mod, "MEDIATOR", True)
    monkeypatch.setattr(game_mod, "_load_historian", lambda: None)  # plain verdict, no model call
    asked = []

    async def decide(view):
        asked.append(view.nation)
        return LeaderOutput(public_statement="", private_intent="", actions=[], followed_advice=True, reason="ok")

    async def go():
        g = Game(seed=7, decide=decide, needle=False)
        s = g.reset(7, Seat(role="mediator", nation=None))
        assert s.available_roles == ["president", "mediator"]
        assert all(n.beliefs is not None for n in s.nations.values())
        await g.turn()
        assert sorted(asked) == sorted(["valdoria", "ostrava", "kessaria", "nordhaven", "zarnia"])
        g.start_crisis("one_berth")
        while g.state.phase == "crisis":
            s = await g.turn()
            if s.crisis and s.crisis.tick == 1:
                out = CallOutput(reply_text="ok", emotion="calm", promises=[{"to": "ostrava", "what": "berth", "when": "morning"}],
                                 belief_updates={"trust_in_player": 0.1, "resolve_of_player": 0})
                g.apply_call("ostrava", out, interrupted=True)  # no home nation: no relations penalty, no crash
        decided = next(e for e in g.state.events if e.type == "crisis_resolved").model_extra["decisions"]
        assert "valdoria" in decided
        return g.end()
    s = asyncio.run(go())
    State.model_validate(s.model_dump(mode="json", by_alias=True))
    sc = s.ending.score
    assert sc.peaceful_crises is not None and 0 <= sc.average_trust <= 1
    assert "mediator" in s.ending.verdict


def test_president_score_shape_unchanged():
    g = Game(seed=7, use_agents=False, needle=False)
    sc = g.end().ending.score
    assert sc.peaceful_crises is None and sc.average_trust is None
