"""Mediator sees public positions only, enforced by the backend (DECIDED 13:17)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from engine import game as game_mod
from engine.app import app
from engine.game import GAME


def test_mediator_sees_no_private_fields_or_beliefs(monkeypatch):
    monkeypatch.setattr(game_mod, "MEDIATOR", True)
    GAME._decide_fn = None
    c = TestClient(app)
    s = c.post("/start", json={"seed": 7, "seat": {"role": "mediator", "nation": None}}).json()
    assert all(n["beliefs"] is None for n in s["nations"].values())
    c.post("/turn")
    for path in ("/state", "/api/state"):
        assert all(n["beliefs"] is None for n in c.get(path).json()["nations"].values())
    d = c.get("/leaders/ostrava").json()
    assert d["private_intent"] == "" and d["advice"] == [] and d["chosen"] == [] and d["reason"] == ""
    assert d["persona"] == "" and d["private_strategy"] is None
    assert GAME.state.nations["ostrava"].beliefs is not None  # the engine still scores with them
    s = c.post("/crisis/start", json={"id": "one_berth"}).json()
    assert all(n["beliefs"] is None for n in s["nations"].values())
    e = c.post("/end").json()
    assert e["ending"]["score"]["average_trust"] is not None  # the mediator's own score is fine


def test_president_still_sees_intel():
    GAME._decide_fn = None
    c = TestClient(app)
    s = c.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}).json()
    assert s["nations"]["ostrava"]["beliefs"] is not None
    c.post("/turn")
    assert c.get("/leaders/ostrava").json()["advice"]
