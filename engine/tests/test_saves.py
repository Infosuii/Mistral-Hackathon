from fastapi.testclient import TestClient

from engine.app import app
from engine.game import GAME


def test_slot_restores_active_crisis_and_log(monkeypatch, tmp_path):
    monkeypatch.setenv("GAMBIT_SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(GAME, "_decide_fn", None)
    with TestClient(app) as client:
        client.post("/start", json={"seed": 912, "seat": {"role": "president", "nation": "valdoria"}})
        assert client.post("/crisis/start", json={"id": "one_berth"}).status_code == 200
        before = client.post("/turn").json()
        events = client.get("/history").json()
        save = client.post("/saves", json={"name": "Before negotiations"})
        assert save.status_code == 201
        slot = save.json()
        assert slot["seed"] == 912
        assert client.get("/saves").json()[0]["id"] == slot["id"]

        client.post("/start", json={"seed": 3, "seat": {"role": "president", "nation": "valdoria"}})
        load = client.post(f"/saves/{slot['id']}/load")
        assert load.status_code == 200
        assert load.json() == before
        assert client.get("/history").json() == events
        assert client.post("/turn").json()["crisis"]["tick"] == 2
