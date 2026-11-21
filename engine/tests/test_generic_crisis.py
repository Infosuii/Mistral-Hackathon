"""Crisis files without a custom resolver (V4): outcomes come from rules in the file."""

from __future__ import annotations

import json

import pytest

from contracts.models import Action, Seat, State
from engine import crisis as cr
from engine.core import new_game, step

BORDER = {
    "id": "border_test", "title": "Border Shots", "ticks_total": 4,
    "intro_news": "Shots across the Zarnia–Kessaria border.",
    "deadlines": {"zarnia": 2, "kessaria": 3, "valdoria": 4, "ostrava": 4, "nordhaven": 4},
    "actions": {"zarnia": ["mobilise", "stand_down"], "kessaria": ["mobilise", "apologise"],
                "valdoria": ["mediate", "stay_out"], "ostrava": ["wait"], "nordhaven": ["wait"]},
    "rules": {
        "public_backdown_cost": {"one_party": 2, "monarchy": 1},
        "payoffs": {"zarnia": {"mobilise": {"base": 1, "low_resolve": 2}, "stand_down": {"base": 0}},
                    "kessaria": {"mobilise": {"base": -1}, "apologise": {"base": 1}},
                    "valdoria": {"mediate": {"base": 1}, "stay_out": {"base": 0}}},
        "outcomes": [
            {"when": {"zarnia": "mobilise", "kessaria": "mobilise"},
             "effects": {"war": ["kessaria", "zarnia"], "news": "The border war begins."}},
            {"when": {"zarnia": "mobilise", "kessaria": "apologise"},
             "effects": {"stats": {"kessaria": {"stability": -5}}, "relations": {"kessaria|zarnia": -10}}},
            {"when": {"zarnia": "stand_down"},
             "effects": {"relations": {"kessaria|zarnia": 10}, "news": "Zarnia stands down."}},
            {"when": {"valdoria": "mediate"}, "effects": {"stats": {"valdoria": {"approval": 3}}}},
        ],
    },
    "scripted": [{"tick": 1, "type": "incoming_call", "from": "zarnia", "emotion": "tense",
                  "opening_line": "Kessaria fired first."}],
}


@pytest.fixture
def border(tmp_path, monkeypatch):
    (tmp_path / "border_test.json").write_text(json.dumps(BORDER))
    monkeypatch.setattr(cr, "CRISES", tmp_path)
    cr.crisis_file.cache_clear()
    yield
    cr.crisis_file.cache_clear()


def run(actions_by_tick: dict[int, list[Action]]) -> State:
    s = cr.start_crisis(new_game(7, Seat(role="president", nation="valdoria")), "border_test")
    while s.phase == "crisis":
        s = step(s, actions_by_tick.get(s.crisis.tick + 1, []), 7)
        State.model_validate(s.model_dump(mode="json", by_alias=True))
    return s


def test_rules_fire_on_matching_decisions(border):
    s = run({2: [Action(type="mobilise", by="zarnia")], 3: [Action(type="mobilise", by="kessaria")]})
    assert any(l.type == "war" and {l.a, l.b} == {"kessaria", "zarnia"} for l in s.links)
    resolved = next(e for e in s.events if e.type == "crisis_resolved")
    assert resolved.model_extra["war"] and "The border war begins." in s.news[-1].text


def test_other_branch_and_advisers_fill_missing_decisions(border):
    base = new_game(7, Seat(role="president", nation="valdoria"))
    s = run({2: [Action(type="stand_down", by="zarnia")]})
    assert s.relations["kessaria|zarnia"] > base.relations["kessaria|zarnia"] - 2  # +10, minus the monthly drift never applied
    assert not any(l.type == "war" for l in s.links)
    decisions = next(e for e in s.events if e.type == "crisis_resolved").model_extra["decisions"]
    assert set(decisions) == set(BORDER["actions"])  # everyone decided, by the end at the latest


def test_new_files_load_through_the_endpoint(border, monkeypatch):
    from engine import game as game_mod
    monkeypatch.setattr(game_mod, "EXTRA_CRISES", True)
    assert "border_test" in cr.available()
    from fastapi.testclient import TestClient
    from engine.app import app
    from engine.game import GAME
    GAME._decide_fn = None
    c = TestClient(app)
    c.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}})
    assert c.post("/crisis/start", json={"id": "border_test"}).status_code == 200
    for _ in range(4):
        r = c.post("/turn").json()
    assert r["phase"] == "strategy"
