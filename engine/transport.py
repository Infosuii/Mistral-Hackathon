"""Road haulage and scheduled air services, derived from the authored atlas.

Both networks follow the same rules as rail: a link that crosses a border runs only under
an active trade agreement and closes the moment the two owners are at war. Everything here
is a pure function of State plus the checked-in data files, so a restored save recomputes
the same services the renderer draws.

Roads (data/infrastructure.json) join neighbouring provinces over land, with bridges where
they cross a river. Each nation hauls county freight from its cities to a hub (its capital,
or its largest remaining city) along the quickest open roads. Travel time is road length
over biome speed, so floodplain and highland routes deliver less than open farmland, and
water with no road across it carries nothing at all.

Air services join airfields (buildings of kind "airfield"). Aircraft cross water, so an
island reaches a trading partner by air when no road can. Highland and floodplain fields
handle less traffic.
"""

from __future__ import annotations

import heapq
import json
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Any

from contracts.models import NATION_IDS, State, relation_key

DATA = Path(__file__).resolve().parent.parent / "data"

MOTORWAY_PACE = 1.0
ROAD_PACE = .72
# Haulage arriving within this much motorway-equivalent travel arrives in full. Measured in
# authored map units, so it multiplies by the generated world's scale (infrastructure.json).
FULL_DELIVERY_TIME = 240.0
DOMESTIC_HAUL = .06    # share of a domestic city's monthly output that road haulage adds
BORDER_HAUL = .04      # GDP each side earns per foreign city a hub reaches across an open border
DOMESTIC_FLIGHT = .08  # GDP per domestic air service, per month
FOREIGN_FLIGHT = .16   # GDP each partner earns per international air service, per month
AIRFIELD_CAPACITY = {"highlands": .7, "marsh": .85, "taiga": .85}


@lru_cache(maxsize=None)
def _load(name: str) -> dict[str, Any]:
    return json.loads((DATA / name).read_text())


def _resource(city: dict) -> str:
    return "gdp" if city["resource"] == "economy" else city["resource"]


def open_pairs(s: State) -> set[str]:
    """Relation keys whose shared borders are open to transport: trading and not at war."""
    wars = {relation_key(link.a, link.b) for link in s.links if link.type == "war"}
    trade = {relation_key(link.a, link.b) for link in s.links if link.type == "trade"}
    return trade - wars


def _passable(owner_a: str | None, owner_b: str | None, allowed: set[str]) -> bool:
    if not owner_a or not owner_b:
        return False
    return owner_a == owner_b or relation_key(owner_a, owner_b) in allowed


def open_roads(s: State, allowed: set[str] | None = None) -> list[dict]:
    allowed = open_pairs(s) if allowed is None else allowed
    return [road for road in _load("infrastructure.json")["roads"]
            if _passable(s.provinces.get(road["a"]), s.provinces.get(road["b"]), allowed)]


def travel_time(road: dict) -> float:
    pace = MOTORWAY_PACE if road["kind"] == "motorway" else ROAD_PACE
    return road["length"] / (road["speed"] * pace)


def hub_of(s: State, nation: str) -> str | None:
    """The capital while the nation holds it, otherwise its most productive remaining city."""
    cities = _load("rail.json")["cities"]
    owned = [p for p in cities if s.provinces.get(p) == nation]
    if not owned:
        return None
    return max(owned, key=lambda p: (cities[p]["capital"] and world_owner(p) == nation, cities[p]["output"], p))


def world_owner(province: str) -> str | None:
    return _load("nations.json")["provinces"].get(province)


def _quickest(start: str, roads: list[dict]) -> tuple[dict[str, float], dict[str, str]]:
    """Dijkstra over open roads: travel time to each province and the road used to reach it."""
    graph: dict[str, list[tuple[str, dict]]] = {}
    for road in roads:
        graph.setdefault(road["a"], []).append((road["b"], road))
        graph.setdefault(road["b"], []).append((road["a"], road))
    times, via = {start: 0.0}, {}
    queue = [(0.0, start)]
    while queue:
        time, province = heapq.heappop(queue)
        if time != times[province]:
            continue
        for neighbour, road in graph.get(province, []):
            arrival = time + travel_time(road)
            if arrival < times.get(neighbour, float("inf")) - 1e-9:
                times[neighbour], via[neighbour] = arrival, road
                heapq.heappush(queue, (arrival, neighbour))
    return times, via


def road_haulage(s: State) -> tuple[list[str], dict[str, dict[str, float]], dict[str, list[dict]]]:
    """Open road services, monthly income by nation, and each hub's deliveries.

    A delivery is {"city", "hub", "time", "share"}; share is the fraction of the haul that
    arrives, 1.0 within FULL_DELIVERY_TIME and falling with slower travel beyond it."""
    allowed = open_pairs(s)
    roads = open_roads(s, allowed)
    cities = _load("rail.json")["cities"]
    used: set[str] = set()
    income: dict[str, dict[str, float]] = {}
    deliveries: dict[str, list[dict]] = {}

    def credit(nation: str, resource: str, amount: float) -> None:
        amounts = income.setdefault(nation, {})
        amounts[resource] = amounts.get(resource, 0.0) + amount

    for nation in NATION_IDS:
        hub = hub_of(s, nation)
        if not hub:
            continue
        times, via = _quickest(hub, roads)
        for city in sorted(cities):
            if city == hub or city not in times:
                continue
            owner = s.provinces.get(city)
            share = min(1.0, FULL_DELIVERY_TIME * _load("infrastructure.json").get("scale", 1) / times[city])
            if owner == nation:
                credit(nation, _resource(cities[city]), DOMESTIC_HAUL * cities[city]["output"] * share)
            else:
                credit(nation, "gdp", BORDER_HAUL * cities[city]["output"] * share)
                credit(owner, "gdp", BORDER_HAUL * cities[city]["output"] * share)
            deliveries.setdefault(nation, []).append(
                {"city": city, "hub": hub, "time": round(times[city]), "share": round(share, 2)})
            step = city
            while step != hub:
                road = via[step]
                used.add(road["id"])
                step = road["a"] if road["b"] == step else road["b"]
    order = [road["id"] for road in _load("infrastructure.json")["roads"] if road["id"] in used]
    return order, _rounded(income), deliveries


def airfields(s: State) -> list[str]:
    return sorted({b.province for b in s.buildings if b.kind == "airfield" and s.provinces.get(b.province)})


def air_capacity(province: str) -> float:
    return AIRFIELD_CAPACITY.get(_load("infrastructure.json")["regions"].get(province, ""), 1.0)


def air_routes(s: State) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Scheduled services between every pair of airfields whose owners may fly to each other."""
    allowed = open_pairs(s)
    services, income = [], {}
    for a, b in combinations(airfields(s), 2):
        owner_a, owner_b = s.provinces[a], s.provinces[b]
        if not _passable(owner_a, owner_b, allowed):
            continue
        services.append(f"{a}|{b}")
        capacity = min(air_capacity(a), air_capacity(b))
        if owner_a == owner_b:
            income.setdefault(owner_a, {}).setdefault("gdp", 0.0)
            income[owner_a]["gdp"] += DOMESTIC_FLIGHT * capacity
        else:
            for owner in (owner_a, owner_b):
                income.setdefault(owner, {}).setdefault("gdp", 0.0)
                income[owner]["gdp"] += FOREIGN_FLIGHT * capacity
    return services, _rounded(income)


def _rounded(income: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {nation: {resource: round(value, 2) for resource, value in sorted(amounts.items()) if round(value, 2)}
            for nation, amounts in sorted(income.items())}


def update_services(s: State) -> None:
    """Recompute which road and air services run, without crediting anything."""
    s.road_services, s.road_income, _ = road_haulage(s)
    s.air_services, s.air_income = air_routes(s)
