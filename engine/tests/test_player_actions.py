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
    assert r.actions and {a.type for a in r.actions} <= {"set_tariff", "declare_war", "make_peace", "leave_alliance", "deploy_fleet", "recall_fleet"}
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

def test_leave_alliance_before_declaring_war(c):
    def options():
        return [a for a in c.get("/actions").json()["actions"] if a["target"] == "nordhaven"]

    assert not any(a["type"] == "declare_war" for a in options())
    leave = next(a for a in options() if a["type"] == "leave_alliance")
    assert c.post("/action", json=leave).status_code == 200
    state = c.post("/turn").json()
    assert not any(link["type"] == "alliance" and {link["a"], link["b"]} == {"nordhaven", "valdoria"}
                   for link in state["links"])
    assert any(a["type"] == "declare_war" for a in options())
    assert any(e["type"] == "alliance_left" for e in c.get("/history").json())

def test_fleet_deploys_blockades_and_returns(c):
    def queue(type_, target):
        options = c.get("/actions").json()["actions"]
        action = next(a for a in options if a["type"] == type_ and a["target"] == target)
        assert c.post("/action", json=action).status_code == 200

    # Deliberately use the pure turn engine so the opponent cannot make peace
    # during this check of the fleet's order, travel, and return.
    from engine.core import step

    def advance():
        with_order = [GAME.player_action] if GAME.player_action else []
        GAME.player_action = None
        GAME.state = step(GAME.state, with_order, GAME.state.seed)
        return GAME.state

    queue("declare_war", "ostrava")
    advance()
    queue("deploy_fleet", "ostrava")
    outbound = advance()
    fleet = outbound.fleets["valdoria"]
    assert fleet.target == "ostrava" and fleet.arrival_turn == outbound.turn + 1
    arrived = advance()
    assert any(e.type == "blockade_started" and e.turn == arrived.turn for e in arrived.events)
    queue("recall_fleet", "ostrava")
    returning = advance()
    assert returning.fleets["valdoria"].returning
    assert "valdoria" not in advance().fleets

def test_county_output_moves_with_control():
    from engine.core import _county_yields, new_game, step
    from contracts.models import Seat

    start = new_game(7, Seat(role="president", nation="valdoria"))
    assert set(_county_yields()) == set(start.provinces)
    captured = start.model_copy(deep=True)
    captured.provinces["p05"] = "nordhaven"  # One half of food-producing Mill Country.
    captured.nations["nordhaven"].stats.territory += 1
    captured.nations["valdoria"].stats.territory -= 1
    ordinary = step(start, [], 7)
    shifted = step(captured, [], 7)
    assert shifted.nations["nordhaven"].stats.food > ordinary.nations["nordhaven"].stats.food
    assert shifted.nations["valdoria"].stats.food < ordinary.nations["valdoria"].stats.food
