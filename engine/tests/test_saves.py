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


def test_restore_isolates_calls_and_round_trips_private_state(tmp_path, monkeypatch):
    import json
    import pytest
    from contracts.models import Action
    from engine import saves
    from engine.game import Game

    monkeypatch.setenv("GAMBIT_SAVE_DIR", str(tmp_path))
    game = Game(use_agents=False)
    deal = Action(type="set_tariff", by="kessaria", target="valdoria", params={"pct": 10})
    game.queued.append(deal)
    game.intent_history["kessaria"] = ["month 0: open trade"]
    game.start_crisis("one_berth")
    info = saves.create(game, "During crisis")
    stale = game.begin_call("ostrava")
    generation = game.call_generation

    saves.restore(game, info.id)
    assert game.call_generation > generation and stale not in game.call_results
    assert game.monthly_deals == [deal]
    assert game.intent_history["kessaria"] == ["month 0: open trade"]

    # Slots written before session history was added still open with an empty history.
    slot = tmp_path / f"{info.id}.json"
    data = json.loads(slot.read_text())
    del data["intent_history"], data["monthly_deals"]
    slot.write_text(json.dumps(data))
    saves.restore(game, info.id)
    assert game.intent_history["kessaria"] == [] and game.monthly_deals == []

    game.begin_call("kessaria")
    latest = game.begin_call("zarnia")
    from contracts.models import CallOutput
    game.apply_call("zarnia", CallOutput(reply_text="Agreed.", emotion="calm",
                    belief_updates={"trust_in_player": 0, "resolve_of_player": 0}), call_id=latest)
    with pytest.raises(ValueError, match="wait"):
        saves.create(game, "Earlier call still pending")
