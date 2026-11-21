"""Road haulage and air services follow ownership, diplomacy, terrain and the atlas."""

import json

from fastapi.testclient import TestClient

from contracts.models import Building, Link, Seat
from engine.core import _load, _road_and_air, new_game, step, update_rail_services
from engine.transport import air_routes, open_roads, road_haulage, travel_time

ROADS = {road["id"]: road for road in _load("infrastructure.json")["roads"]}


def fresh():
    return new_game(7, Seat(role="president", nation="valdoria"))


def test_haulage_runs_on_generated_roads_and_credits_exactly_what_it_reports():
    state = fresh()
    assert state.road_services and set(state.road_services) <= set(ROADS)
    # Every running road joins provinces with the same owner at the start: no border is open by road yet.
    assert all(state.provinces[ROADS[r]["a"]] == state.provinces[ROADS[r]["b"]] for r in state.road_services)
    before = {n: state.nations[n].stats.model_dump() for n in state.nations}
    _road_and_air(state)
    credited = {}
    for income in (state.road_income, state.air_income):
        for nation, amounts in income.items():
            for resource, amount in amounts.items():
                credited[(nation, resource)] = credited.get((nation, resource), 0) + amount
    for (nation, resource), amount in credited.items():
        assert round(getattr(state.nations[nation].stats, resource) - before[nation][resource], 6) == round(amount, 6)
    assert state.road_income["valdoria"]["food"] > 0  # Mill Country's grain reaches Valdor Basin


def test_trade_opens_a_border_road_and_war_closes_it():
    state = fresh()
    assert not any(state.provinces[ROADS[r]["a"]] != state.provinces[ROADS[r]["b"]] for r in state.road_services)
    state.links.append(Link(type="trade", a="kessaria", b="valdoria"))
    services, income, deliveries = road_haulage(state)
    crossing = [r for r in services if {state.provinces[ROADS[r]["a"]], state.provinces[ROADS[r]["b"]]} == {"kessaria", "valdoria"}]
    assert crossing, "a trade agreement should carry haulage across the shared border"
    assert any(state.provinces[d["city"]] == "kessaria" for d in deliveries["valdoria"])
    assert income["kessaria"]["gdp"] > 0 and income["valdoria"]["gdp"] > 0

    state.links.append(Link(type="war", a="kessaria", b="valdoria"))
    services, _, deliveries = road_haulage(state)
    assert not set(crossing) & set(services)
    assert all(state.provinces[d["city"]] == "valdoria" for d in deliveries["valdoria"])
    assert not set(crossing) & {road["id"] for road in open_roads(state)}


def test_water_stops_roads_but_not_aircraft():
    state = fresh()  # Valdoria and Nordhaven trade, but Nordhaven is an island
    _, _, deliveries = road_haulage(state)
    assert all(state.provinces[d["city"]] != "nordhaven" for d in deliveries["valdoria"])
    assert not any("nordhaven" in {state.provinces[r["a"]], state.provinces[r["b"]]} and "valdoria" in
                   {state.provinces[r["a"]], state.provinces[r["b"]]} for r in ROADS.values())
    services, income = air_routes(state)
    assert "p06|p35" in services  # Pinewatch airfield to Nordhaven's field
    assert income["valdoria"]["gdp"] > 0 and income["nordhaven"]["gdp"] > 0

    state.links.append(Link(type="war", a="nordhaven", b="valdoria"))
    services, income = air_routes(state)
    assert "p06|p35" not in services and "valdoria" not in income


def test_slower_terrain_delivers_less():
    marsh = next(r for r in ROADS.values() if r["speed"] < .7)
    farm = next(r for r in ROADS.values() if r["speed"] == 1 and r["kind"] == marsh["kind"])
    assert travel_time(marsh) / marsh["length"] > travel_time(farm) / farm["length"]
    _, _, deliveries = road_haulage(fresh())
    shares = [d["share"] for ds in deliveries.values() for d in ds]
    assert min(shares) < 1 <= max(shares)


def test_new_airfield_adds_domestic_service_and_capture_moves_it():
    state = fresh()
    state.buildings.append(Building(province="p04", kind="airfield", built_turn=1))
    update_rail_services(state)
    assert "p04|p06" in state.air_services and "p04|p35" in state.air_services
    state.provinces["p06"] = "kessaria"  # Kessaria captures Pinewatch and its airfield
    update_rail_services(state)
    assert "p04|p06" not in state.air_services
    assert "p06|p11" in state.air_services  # Kessaria's new field joins its Ostrava trade service
    assert state.road_services and all(state.provinces[ROADS[r]["a"]] and state.provinces[ROADS[r]["b"]]
                                       for r in state.road_services)


def test_hub_falls_back_when_the_capital_is_lost():
    state = fresh()
    state.provinces["p01"] = "kessaria"
    _, _, deliveries = road_haulage(state)
    assert deliveries["valdoria"] and all(d["hub"] == "p04" for d in deliveries["valdoria"])  # Mill Country


def test_monthly_step_keeps_services_current():
    state = fresh()
    state.links.append(Link(type="trade", a="kessaria", b="valdoria"))
    later = step(state, [], 7)
    assert any({later.provinces[ROADS[r]["a"]], later.provinces[ROADS[r]["b"]]} == {"kessaria", "valdoria"}
               for r in later.road_services)
    assert later.road_income and later.air_income


def test_old_save_without_transport_fields_restores_services(monkeypatch, tmp_path):
    from engine.app import app
    from engine.game import GAME

    monkeypatch.setenv("GAMBIT_SAVE_DIR", str(tmp_path))
    monkeypatch.setattr(GAME, "_decide_fn", None)
    with TestClient(app) as client:
        client.post("/start", json={"seed": 5, "seat": {"role": "president", "nation": "valdoria"}})
        expected = client.get("/state").json()
        slot = client.post("/saves", json={"name": "Before roads"}).json()
        path = tmp_path / f"{slot['id']}.json"
        record = json.loads(path.read_text())
        for field in ("road_services", "road_income", "air_services", "air_income"):
            record["state"].pop(field)
        path.write_text(json.dumps(record))
        restored = client.post(f"/saves/{slot['id']}/load").json()
        for field in ("road_services", "air_services"):
            assert restored[field] == expected[field] and restored[field]
