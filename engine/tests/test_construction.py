from fastapi.testclient import TestClient

from engine.app import app
from engine.core import _load, borders, new_game
from engine.game import GAME
from contracts.models import Seat


def test_atlas_has_channels_with_no_land_fronts():
    start = new_game(7, Seat(role="president", nation="valdoria"))
    assert not borders(start, "valdoria", "nordhaven")
    assert not borders(start, "valdoria", "ostrava")
    assert borders(start, "ostrava", "zarnia")
    nav = _load("sea_routes.json")
    path = nav["routes"]["nordhaven|valdoria"]
    assert path[0] == nav["ports"]["nordhaven"]["position"]
    assert path[-1] == nav["ports"]["valdoria"]["position"]


def test_orders_create_starter_infrastructure_and_complete_project(monkeypatch, tmp_path):
    monkeypatch.setenv("GAMBIT_SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(GAME, "_decide_fn", None)
    with TestClient(app) as client:
        begin = client.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}).json()
        assert len(begin["buildings"]) == 15
        foreign = {"province": "p09", "kind": "farm"}
        duplicate = {"province": "p02", "kind": "army_base"}
        assert client.post("/construction", json=foreign).status_code == 409
        assert client.post("/construction", json=duplicate).status_code == 409
        order = {"province": "p01", "kind": "farm"}
        queued = client.post("/construction", json=order).json()
        assert queued["construction"] == order
        assert queued["nations"]["valdoria"]["stats"] == begin["nations"]["valdoria"]["stats"]
        slot = client.post("/saves", json={"name": "Before building"}).json()["id"]
        client.post("/start", json={"seed": 1, "seat": {"role": "president", "nation": "valdoria"}})
        assert client.post(f"/saves/{slot}/load").json()["construction"] == order
        result = client.post("/turn").json()
        assert result["construction"] is None
        assert {**order, "built_turn": 1} in result["buildings"]
        assert any(e["type"] == "construction_completed" for e in client.get("/history").json())
