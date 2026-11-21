"""Grey Fever (data/crises/outbreak.json, Ashish) behind GAMBIT_EXTRA_CRISES (DECIDED 13:12)."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from contracts.models import CallOutput, State
from engine import game as game_mod
from engine.app import app
from engine.game import GAME, Game


def _promise(to, what, when="now"):
    return CallOutput(reply_text="...", emotion="calm", belief_updates={"trust_in_player": 0, "resolve_of_player": 0},
                      promises=[{"to": to, "what": what, "when": when}])


def play(calls: dict[int, list[tuple[str, CallOutput]]]) -> State:
    async def go():
        g = Game(seed=7, use_agents=False, needle=False)
        g.start_crisis("outbreak")
        while g.state.phase == "crisis":
            s = await g.turn()
            State.model_validate(s.model_dump(mode="json", by_alias=True))
            for to, out in calls.get(s.crisis.tick if s.crisis else -1, []):
                g.apply_call(to, out)
        return g.state
    return asyncio.run(go())


def _resolved(s):
    return next(e for e in reversed(s.events) if e.type == "crisis_resolved").model_extra


def test_doing_nothing_ends_in_war():
    assert _resolved(play({}))["war"]


def test_honest_first_doses_to_zarnia_prevents_war():
    r = _resolved(play({1: [("zarnia", _promise("zarnia", "first doses"))]}))
    assert not r["war"], r["decisions"]


def test_same_promise_to_both_is_caught():
    s = play({1: [("zarnia", _promise("zarnia", "first_doses"))], 3: [("kessaria", _promise("kessaria", "first_doses"))]})
    assert any("compare notes" in n.text and "both" in n.text for n in s.news)


def test_offered_only_when_the_flag_is_on(monkeypatch):
    GAME._decide_fn = None
    c = TestClient(app)
    seat = {"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}
    s = c.post("/start", json=seat).json()
    assert s["available_crises"] is None
    assert c.post("/crisis/start", json={"id": "outbreak"}).status_code == 404
    monkeypatch.setattr(game_mod, "EXTRA_CRISES", True)
    s = c.post("/start", json=seat).json()
    assert s["available_crises"][0] == {"id": "one_berth", "title": "One Berth"}
    assert {"id": "outbreak", "title": "Grey Fever"} in s["available_crises"]
    assert c.post("/crisis/start", json={"id": "outbreak"}).status_code == 200
