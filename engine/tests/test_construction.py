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
        assert queued["construction_queue"] == [order]
        cost = _load("buildings.json")["kinds"]["farm"]["cost"]
        for stat, price in cost.items():  # paid when ordered
            assert queued["nations"]["valdoria"]["stats"][stat] == begin["nations"]["valdoria"]["stats"][stat] - price
        slot = client.post("/saves", json={"name": "Before building"}).json()["id"]
        client.post("/start", json={"seed": 1, "seat": {"role": "president", "nation": "valdoria"}})
        assert client.post(f"/saves/{slot}/load").json()["construction_queue"] == [order]
        result = client.post("/turn").json()
        assert result["construction_queue"] == []
        assert {**order, "built_turn": 1} in result["buildings"]
        assert any(e["type"] == "construction_completed" for e in client.get("/history").json())

def test_city_freight_uses_shared_routes_and_credits_resources():
    from contracts.models import Link
    from engine.core import _active_rail, _rail_freight, relation_key

    state = new_game(7, Seat(role="president", nation="valdoria"))
    definitions = _load("rail.json")
    adjacency = _load("atlas_adjacency.json")
    route = next(route for route in definitions["routes"]
                 if state.provinces[route["from"]] != state.provinces[route["to"]])
    assert route["from"] in definitions["cities"] and route["to"] in definitions["cities"]
    assert all(b in adjacency[a] for a, b in zip(route["via"], route["via"][1:]))
    owners = [state.provinces[province] for province in route["via"]]
    pairs = {relation_key(a, b) for a, b in zip(owners, owners[1:]) if a != b}
    state.links = [Link(type="trade", a=a, b=b) for a, b in (key.split("|") for key in sorted(pairs))]
    assert route in _active_rail(state)
    before = state.nations["valdoria"].stats.model_dump()
    _rail_freight(state)
    assert route["id"] in state.rail_services
    for stat, amount in state.rail_income["valdoria"].items():
        assert getattr(state.nations["valdoria"].stats, stat) == before[stat] + amount
    a, b = min(pairs).split("|")
    state.links.append(Link(type="war", a=a, b=b))
    assert route not in _active_rail(state)


def test_several_projects_queue_in_one_month_and_cancel_refunds(monkeypatch):
    monkeypatch.setattr(GAME, "_decide_fn", None)
    with TestClient(app) as client:
        begin = client.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}}).json()
        orders = [{"province": "p01", "kind": "farm"}, {"province": "p01", "kind": "factory"},
                  {"province": "p03", "kind": "farm"}]
        for order in orders:
            state = client.post("/construction", json=order)
            assert state.status_code == 200, state.json()
        assert state.json()["construction_queue"] == orders
        again = client.post("/construction", json=orders[0])
        assert again.status_code == 409 and "queued" in again.json()["detail"]
        refunded = client.post("/construction/cancel", json=orders[1]).json()
        assert refunded["construction_queue"] == [orders[0], orders[2]]
        assert client.post("/construction/cancel", json=orders[1]).status_code == 409
        spent = refunded["nations"]["valdoria"]["stats"]["gdp"]
        assert spent == begin["nations"]["valdoria"]["stats"]["gdp"] - 2 * _load("buildings.json")["kinds"]["farm"]["cost"]["gdp"]
        result = client.post("/turn").json()
        built = {(b["province"], b["kind"]) for b in result["buildings"]}
        assert {("p01", "farm"), ("p03", "farm")} <= built and ("p01", "factory") not in built


def test_unaffordable_project_names_what_is_short():
    from engine.core import queue_project
    from contracts.models import BuildRequest
    state = new_game(7, Seat(role="president", nation="valdoria"))
    state.nations["valdoria"].stats.chips = 0
    try:
        queue_project(state, BuildRequest(province="p01", kind="factory"))
    except ValueError as e:
        assert "chips" in str(e)
    else:
        raise AssertionError("expected the project to be refused")


def test_war_front_and_conquest_disrupt_output():
    from contracts.models import Link
    from engine.core import _monthly, disrupted_provinces, weights, _Log
    import random

    state = new_game(7, Seat(role="president", nation="valdoria"))
    assert disrupted_provinces(state) == []
    state.links.append(Link(type="war", a="ostrava", b="zarnia"))
    front = disrupted_provinces(state)
    adjacency = _load("atlas_adjacency.json")
    assert front and all(any(state.provinces[q] != state.provinces[p] and state.provinces[q] in ("ostrava", "zarnia")
                             for q in adjacency[p]) for p in front)
    assert {state.provinces[p] for p in front} == {"ostrava", "zarnia"}

    # the same month with and without the war: the front costs both sides output
    calm = new_game(7, Seat(role="president", nation="valdoria"))
    w = weights()
    _monthly(calm, random.Random(1), w, _Log(1))
    _monthly(state, random.Random(1), w, _Log(1))
    assert state.disrupted == front
    for nation in ("ostrava", "zarnia"):
        lost = sum(getattr(calm.nations[nation].stats, r) - getattr(state.nations[nation].stats, r)
                   for r in ("gdp", "oil", "food", "chips"))
        assert lost > 0, nation

    # a captured province is in unrest for two months, then produces in full for its new owner
    conquered = new_game(7, Seat(role="president", nation="valdoria"))
    province = next(p for p, owner in conquered.provinces.items() if owner == "zarnia")
    conquered.provinces[province] = "ostrava"
    conquered.unrest[province] = w["war"]["capture_unrest_months"]
    seen = []
    for month in range(3):
        _monthly(conquered, random.Random(month), w, _Log(month))
        seen.append(province in conquered.disrupted)
    assert seen == [True, True, False]


def test_older_save_single_slot_is_not_built_or_charged_twice(monkeypatch, tmp_path):
    """Coordinator 16:31: a save with one farm in the old single slot, then the same farm queued
    again, built two farms and charged twice."""
    from contracts.models import BuildRequest
    monkeypatch.setenv("GAMBIT_SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(GAME, "_decide_fn", None)
    farm = {"province": "p01", "kind": "farm"}
    cost = _load("buildings.json")["kinds"]["farm"]["cost"]
    with TestClient(app) as client:
        client.post("/start", json={"seed": 7, "seat": {"role": "president", "nation": "valdoria"}})
        GAME.state = GAME.state.model_copy(update={"construction": BuildRequest(**farm)})  # as an older build saved it
        slot = client.post("/saves", json={"name": "Old single slot"}).json()["id"]
        client.post("/start", json={"seed": 1, "seat": {"role": "president", "nation": "valdoria"}})
        loaded = client.post(f"/saves/{slot}/load").json()
        assert loaded["construction"] == farm and loaded["construction_queue"] == []
        again = client.post("/construction", json=farm)
        assert again.status_code == 409 and "queued" in again.json()["detail"]
        # its cost is reserved: a new order cannot spend the money the old slot will need
        GAME.state.nations["valdoria"].stats.oil = cost["oil"] + 1
        short = client.post("/construction", json={"province": "p03", "kind": "farm"})
        assert short.status_code == 409 and "oil" in short.json()["detail"]
        GAME.state.nations["valdoria"].stats.oil = 30
        before = GAME.state.nations["valdoria"].stats.gdp
        from engine.core import _advance_construction, _Log
        s = GAME.state.model_copy(deep=True)
        _advance_construction(s, _Log(s.turn))
        farms = [b for b in s.buildings if b.province == "p01" and b.kind == "farm"]
        assert len(farms) == 1 and s.construction is None
        assert s.nations["valdoria"].stats.gdp == before - cost["gdp"]  # charged once, when it opened


def test_already_doubled_save_builds_once_and_refunds_the_copy():
    from contracts.models import BuildRequest
    from engine.core import _advance_construction, _Log
    s = new_game(7, Seat(role="president", nation="valdoria"))
    farm = BuildRequest(province="p01", kind="farm")
    cost = _load("buildings.json")["kinds"]["farm"]["cost"]
    s.construction = farm  # the pre-fix bug: legacy slot plus a paid queue copy
    s.construction_queue = [farm]
    gdp = s.nations["valdoria"].stats.gdp - cost["gdp"]  # the queue copy was paid when ordered
    s.nations["valdoria"].stats.gdp = gdp
    _advance_construction(s, _Log(1))
    assert sum(1 for b in s.buildings if b.province == "p01" and b.kind == "farm") == 1
    assert s.nations["valdoria"].stats.gdp == gdp  # one farm paid for in total


def test_cancel_old_single_slot_without_refund():
    from contracts.models import BuildRequest
    from engine.core import cancel_project
    s = new_game(7, Seat(role="president", nation="valdoria"))
    s.construction = BuildRequest(province="p01", kind="farm")
    after = cancel_project(s, s.construction)
    assert after.construction is None
    assert after.nations["valdoria"].stats == s.nations["valdoria"].stats
