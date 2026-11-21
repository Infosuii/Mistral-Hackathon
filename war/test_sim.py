"""python -m pytest -q war"""
import json
from pathlib import Path

from contracts.models import State, relation_key
from engine.core import new_game
from contracts.models import Seat

from war.sim import CAPITALS, NEIGHBOURS, WarRoom, hop_seconds


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def game():
    return new_game(7, Seat(role="president", nation="valdoria"))


def border_target(s, me, enemy):
    return next(p for p, o in s.provinces.items() if o == enemy
                and any(s.provinces.get(q) == me for q in NEIGHBOURS[p]))


def test_deploy_matches_army():
    s = game()
    room = WarRoom(s, clock=Clock())
    for n, nation in s.nations.items():
        assert abs(room.troops(n, s) - nation.stats.army * 100) < 10
    cap = CAPITALS["ostrava"]
    assert room.garrison[cap] == max(room.garrison[p] for p, o in s.provinces.items() if o == "ostrava")


def test_attack_takes_time_and_stronger_side_wins():
    s, clock = game(), Clock()
    room = WarRoom(s, clock=clock)
    room.declare(s, "valdoria", "kessaria")
    target = border_target(s, "valdoria", "kessaria")
    src = max((q for q in NEIGHBOURS[target] if s.provinces[q] == "valdoria"), key=lambda q: room.garrison[q])
    room.garrison[src] = 9000  # overwhelming force
    army = room.attack(s, "valdoria", target, share=0.9, advance=False)
    room.advance(s)
    assert s.provinces[target] == "kessaria", "troops must not arrive instantly"
    clock.t += hop_seconds(army.src, target) + 0.1
    room.advance(s)
    assert s.provinces[target] == "valdoria"
    assert s.nations["valdoria"].stats.territory == sum(1 for o in s.provinces.values() if o == "valdoria")
    assert any(e["kind"] == "battle" and e["winner"] == "valdoria" for e in room.log)
    State.model_validate(s.model_dump(mode="json", by_alias=True))  # still a valid contract State


def test_weak_attack_is_repelled():
    s, clock = game(), Clock()
    room = WarRoom(s, clock=clock)
    room.declare(s, "valdoria", "nordhaven")
    target = border_target(s, "valdoria", "nordhaven")
    src = next(q for q in NEIGHBOURS[target] if s.provinces[q] == "valdoria")
    room.garrison[src], room.garrison[target] = 200, 5000
    room.attack(s, "valdoria", target, share=1.0, src=src)
    clock.t += 30
    room.advance(s)
    assert s.provinces[target] == "nordhaven"
    assert any(e["kind"] == "battle" and e["winner"] == "nordhaven" and e["province"] == target for e in room.log)


def test_cannot_attack_without_war_or_border():
    s = game()
    room = WarRoom(s, clock=Clock())
    t = border_target(s, "valdoria", "kessaria")
    try:
        room.attack(s, "valdoria", t)
        assert False, "needs a declaration"
    except ValueError as e:
        assert "declare war" in str(e)
    room.declare(s, "valdoria", "ostrava")
    far = next(p for p, o in s.provinces.items() if o == "ostrava"
               and not any(s.provinces.get(q) == "valdoria" for q in NEIGHBOURS[p]))
    try:
        room.attack(s, "valdoria", far)
        assert False, "not on the border"
    except ValueError as e:
        assert "border" in str(e)


def test_advance_continues_into_next_province():
    s, clock = game(), Clock()
    room = WarRoom(s, clock=clock)
    room.declare(s, "valdoria", "kessaria")
    target = border_target(s, "valdoria", "kessaria")
    src = next(q for q in NEIGHBOURS[target] if s.provinces[q] == "valdoria")
    room.garrison[src] = 30000
    room.attack(s, "valdoria", target, share=1.0, src=src)
    clock.t += 60
    room.advance(s)
    clock.t += 60
    room.advance(s)
    taken = sum(1 for e in room.log if e["kind"] == "battle" and e["winner"] == "valdoria")
    assert taken >= 2


def test_recruit_arrives_after_delay_and_costs_economy():
    s, clock = game(), Clock()
    room = WarRoom(s, clock=clock)
    gdp, before = s.nations["valdoria"].stats.gdp, room.troops("valdoria", s)
    room.recruit(s, "valdoria", 1000)
    assert s.nations["valdoria"].stats.gdp == round(gdp - 10, 1)
    room.advance(s)
    assert room.troops("valdoria", s) == before
    clock.t += 6
    room.advance(s)
    assert room.troops("valdoria", s) == before + 1000


def test_peace_terms():
    s, clock = game(), Clock()
    room = WarRoom(s, clock=clock)
    room.declare(s, "valdoria", "ostrava")
    assert room.peace(s, "valdoria", "ostrava", "white")["accepted"]
    assert not any(l.type == "war" for l in s.links)
    room.declare(s, "valdoria", "ostrava")
    room.wars[relation_key("valdoria", "ostrava")].taken["ostrava"] = 3
    assert not room.peace(s, "valdoria", "ostrava", "white")["accepted"]
    assert room.peace(s, "valdoria", "ostrava", "pay", 60)["accepted"]
    s.relations[relation_key("valdoria", "nordhaven")] = 20
    assert room.peace(s, "valdoria", "nordhaven", "pact")["accepted"]


def test_hostile_ai_declares_on_player():
    s, clock = game(), Clock()
    room = WarRoom(s, clock=clock)
    s.relations[relation_key("valdoria", "ostrava")] = -80
    clock.t += 25
    room.advance(s)
    assert room.at_war("ostrava", "valdoria")
    assert any(e["kind"] == "declare" and e["attacker"] == "ostrava" for e in room.log)
