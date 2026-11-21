"""POST /action and GET /actions (DECIDED 13:49), behind GAMBIT_PLAYER_ACTIONS."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from contracts.models import PlayerActions
from engine import game as game_mod
from engine.app import app
from engine.game import GAME

PRESIDENT = {"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}


@pytest.fixture
def c(monkeypatch):
    monkeypatch.setattr(game_mod, "PLAYER_ACTIONS", True)
    GAME._decide_fn = None
    client = TestClient(app)
    client.post("/start", json=PRESIDENT)
    return client


def test_off_by_default():
    GAME._decide_fn = None
    client = TestClient(app)
    assert client.get("/actions").json() == {"actions": [], "queued": None}  # no console 404s
    assert client.post("/action", json={"type": "set_tariff", "by": "valdoria", "target": "ostrava",
                                        "params": {"pct": 10}}).status_code == 404


def test_lists_one_sided_moves_and_queues_one_for_next_month(c):
    r = PlayerActions.model_validate(c.get("/actions").json())
    assert r.actions and {a.type for a in r.actions} <= {"set_tariff", "declare_war", "make_peace"}
    assert all(a.by == "valdoria" for a in r.actions) and r.queued is None
    tariff = next(a for a in r.actions if a.type == "set_tariff" and a.params["pct"] == 25)
    q = c.post("/action", json=tariff.model_dump()).json()
    assert q["queued"]["type"] == "set_tariff"
    other = next(a for a in r.actions if a.type == "set_tariff" and a.params["pct"] == 10)
    assert c.post("/action", json=other.model_dump()).json()["queued"]["params"]["pct"] == 10  # replaces
    s = c.post("/turn").json()
    assert any("Valdoria slaps a 10% tariff" in n["text"] for n in s["news"])
    assert c.get("/actions").json()["queued"] is None


def test_refusals(c):
    trade = {"type": "propose_trade", "by": "valdoria", "target": "nordhaven",
             "params": {"give": {"food": 10}, "get": {"oil": 10}}}
    assert c.post("/action", json=trade).status_code == 400  # needs a phone call
    assert c.post("/action", json={"type": "set_tariff", "by": "ostrava", "target": "valdoria",
                                   "params": {"pct": 10}}).status_code == 400  # not your nation
    assert c.post("/action", json={"type": "make_peace", "by": "valdoria", "target": "ostrava"}).status_code == 400  # not at war
    c.post("/crisis/start", json={"id": "one_berth"})
    assert c.post("/action", json={"type": "set_tariff", "by": "valdoria", "target": "ostrava",
                                   "params": {"pct": 10}}).status_code == 409
    assert c.get("/actions").json()["actions"] == []


def test_mediator_has_no_moves(c, monkeypatch):
    monkeypatch.setattr(game_mod, "MEDIATOR", True)
    c.post("/start", json={"seed": 7, "seat": {"role": "mediator", "nation": None}})
    assert c.get("/actions").json()["actions"] == []
    assert c.post("/action", json={"type": "set_tariff", "by": "valdoria", "target": "ostrava",
                                   "params": {"pct": 10}}).status_code == 400
