"""The pure engine: new_game, legal_actions, advise, step.

step(state, actions, seed) returns a new State and touches nothing else: no globals,
no wall-clock time, no unseeded randomness. All numbers come from data/weights.json
and data/nations.json, which are read once and never modified.
"""

from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from contracts.models import (
    NATION_IDS, Action, Advice, Event, Link, NewsItem, Seat, State, relation_key,
)

DATA = Path(__file__).resolve().parent.parent / "data"
RESOURCES = ("food", "oil", "chips")
STAT_NAMES = ("gdp", "oil", "food", "chips", "army", "stability", "approval")
KEEP_NEWS = 30


@lru_cache(maxsize=None)
def _load(name: str) -> str:
    return (DATA / name).read_text()


def weights() -> dict[str, Any]:
    return json.loads(_load("weights.json"))  # a fresh copy each call, so nobody can mutate it


def world() -> dict[str, Any]:
    return json.loads(_load("nations.json"))


# --- setup -------------------------------------------------------------------


def new_game(seed: int, seat: Seat) -> State:
    w = world()
    nations = {}
    for nid, n in w["nations"].items():
        territory = sum(1 for owner in w["provinces"].values() if owner == nid)
        nations[nid] = {**n, "stats": {**n["stats"], "territory": territory}, "status": []}
        if nid == seat.nation:
            nations[nid]["beliefs"] = None
    state = State.model_validate({
        "turn": 0, "phase": "strategy", "seed": seed, "seat": seat.model_dump(),
        "nations": nations, "relations": w["relations"], "links": w["links"],
        "provinces": w["provinces"],
        "news": [{"turn": 0, "text": "Five nations, one continent. The year begins."}],
    })
    _refresh_status(state, weights())
    return state


# --- small queries -----------------------------------------------------------


def rel(state: State, a: str, b: str) -> int:
    return state.relations.get(relation_key(a, b), 0)


def has_link(state: State, kind: str, a: str, b: str) -> bool:
    pair = {a, b}
    return any(l.type == kind and {l.a, l.b} == pair for l in state.links)


def allies(state: State, nation: str) -> list[str]:
    return sorted(o for o in NATION_IDS if o != nation and has_link(state, "alliance", nation, o))


def borders(state: State, a: str, b: str) -> bool:
    nb = world()["neighbours"]
    return any(state.provinces.get(q) == b
               for p, owner in state.provinces.items() if owner == a for q in nb[p])


def power(state: State, nation: str, w: dict) -> float:
    def own(n: str) -> float:
        s = state.nations[n].stats
        return s.army * (w["war"]["morale_base"] + s.stability / 100)
    return own(nation) + w["war"]["ally_share"] * sum(own(a) for a in allies(state, nation))


def p_win(state: State, a: str, b: str, w: dict) -> float:
    return 1 / (1 + math.exp(-(power(state, a, w) - power(state, b, w)) / 20))


def _recent(state: State, types: tuple[str, ...], nation: str, target: str, months: int) -> bool:
    return any(e.type in types and e.nation == nation and getattr(e, "target", None) == target
               and e.turn > state.turn - months for e in state.events)


def accepts(state: State, a: Action, w: dict) -> bool:
    """The rule an AI target uses to accept a trade or alliance proposal."""
    t = a.target
    if a.type == "propose_alliance":
        return rel(state, a.by, t) >= w["alliance"]["accept_min_relation"]
    mirrored = Action(type="propose_trade", by=t, target=a.by,
                      params={"give": a.params["get"], "get": a.params["give"]})
    return (rel(state, a.by, t) >= w["trade"]["accept_min_relation"]
            and _score(state, mirrored, w, assume_accept=True) > 0)


def p_accept(state: State, a: Action, w: dict) -> float:
    """How likely the proposer's advisers think the target is to accept."""
    t = a.target
    if t == state.seat.nation and state.nations[a.by].beliefs:
        p = state.nations[a.by].beliefs.trust_in_player  # a human decides; trust is the guess
        if _recent(state, ("trade_rejected", "alliance_rejected"), t, a.by, 3):
            p = 0.0  # just said no; don't ask again for a few months
        return p
    return 1.0 if accepts(state, a, w) else 0.0


# --- legal actions -----------------------------------------------------------


def _trade_params(state: State, nation: str, w: dict) -> dict:
    s = state.nations[nation].stats
    ranked = sorted(RESOURCES, key=lambda r: (getattr(s, r), r))
    amount = w["trade"]["amount"]
    return {"give": {ranked[-1]: amount}, "get": {ranked[0]: amount}}


def legal_actions(state: State, nation: str) -> list[Action]:
    if state.phase == "crisis":
        from engine.crisis import crisis_legal
        return crisis_legal(state, nation)
    acts = [Action(type="wait", by=nation)]
    if state.phase != "strategy":
        return acts
    w = weights()
    for t in NATION_IDS:
        if t == nation:
            continue
        if has_link(state, "war", nation, t):
            acts.append(Action(type="make_peace", by=nation, target=t))
            continue
        if not _recent(state, ("tariff",), nation, t, w["tariff"]["cooldown_months"]):
            for pct in w["tariff"]["options_pct"]:
                acts.append(Action(type="set_tariff", by=nation, target=t, params={"pct": pct}))
        if not has_link(state, "trade", nation, t):
            acts.append(Action(type="propose_trade", by=nation, target=t,
                               params=_trade_params(state, nation, w)))
        allied = has_link(state, "alliance", nation, t)
        if not allied and rel(state, nation, t) >= w["alliance"]["min_relation"]:
            acts.append(Action(type="propose_alliance", by=nation, target=t))
        if (not allied and rel(state, nation, t) <= w["war"]["min_relation_to_declare"]
                and borders(state, nation, t)):
            acts.append(Action(type="declare_war", by=nation, target=t))
    return acts


def _key(a: Action) -> tuple:
    return (a.type, a.target or "", json.dumps(a.params, sort_keys=True))


def is_legal(state: State, action: Action) -> bool:
    return any(_key(a) == _key(action) for a in legal_actions(state, action.by))


# --- advise ------------------------------------------------------------------


def _resource_value(level: float, weight: float) -> float:
    """Scarce resources are worth more: twice as much at 0 as at 50."""
    return weight * (1 + (50 - level) / 50)


def _score(state: State, a: Action, w: dict, assume_accept: bool = False) -> float:
    me = state.nations[a.by]
    rw = w["regime_weights"][me.system]
    sc = w["score"]
    h = sc["horizon_months"]
    t = a.target
    if a.type == "wait" or t is None:
        return 0.0

    r = rel(state, a.by, t)
    spite = max(0, -r) / 100
    score = 0.0

    if a.type == "set_tariff":
        pct = a.params["pct"]
        tw = w["tariff"]
        score -= rw["gdp"] * tw["gdp_cost_self_per_pct"] * pct
        score += spite * rw["gdp"] * tw["gdp_cost_target_per_pct"] * pct
        score += sc["relation_value"] * tw["relation_per_pct"] * pct * rw["military"]
        if pct >= tw["breaks_trade_at_pct"] and has_link(state, "trade", a.by, t):
            score -= h * rw["gdp"] * w["trade"]["monthly_gdp"]

    elif a.type == "propose_trade":
        tr = w["trade"]
        gain = h * (rw["gdp"] * tr["monthly_gdp"] + 2 * rw["supply"] * tr["monthly_supply"])
        for res, amt in a.params["get"].items():
            gain += amt * _resource_value(getattr(me.stats, res), rw["supply"] if res != "chips" else rw["gdp"] / 2)
        for res, amt in a.params["give"].items():
            gain -= amt * _resource_value(getattr(me.stats, res), rw["supply"] if res != "chips" else rw["gdp"] / 2)
        p = 1.0 if assume_accept else p_accept(state, a, w)
        score += p * (gain + sc["relation_value"] * tr["relation"])

    elif a.type == "propose_alliance":
        threatened = any(rel(state, a.by, o) < -20 for o in NATION_IDS if o != a.by)
        value = rw["military"] * state.nations[t].stats.army / 10 * (1 if threatened else 0.3)
        score += p_accept(state, a, w) * (value + sc["relation_value"] * w["alliance"]["relation"])

    elif a.type in ("declare_war", "make_peace"):
        wr = w["war"]
        months = h
        cost = months * (rw["military"] * 0.3 * -wr["monthly_army"]
                         + rw["gdp"] * -wr["monthly_gdp"]
                         + rw["stability"] * -wr["monthly_stability"]
                         + (rw["approval"] * -wr["monthly_approval_democracy"] if me.system == "democracy" else 0))
        pw = p_win(state, a.by, t, w)
        gain = (2 * pw - 1) * months * sc["territory_value"] * rw["military"]
        target_food = state.nations[t].stats.food
        gain += pw * wr["plunder"] * _resource_value(me.stats.food, rw["supply"]) * (target_food > me.stats.food)
        if t == state.seat.nation and me.beliefs:
            gain += sc["low_resolve_escalation_bonus"] * (1 - me.beliefs.resolve_of_player)
        war_value = gain - cost
        if has_link(state, "trade", a.by, t):
            war_value -= h * rw["gdp"] * w["trade"]["monthly_gdp"]
        if a.type == "declare_war":
            score += war_value + sc["relation_value"] * wr["relation"] * rw["military"]
        else:
            score += -war_value + sc["relation_value"] * w["peace"]["relation"]

    return round(score, 2)


def advise(state: State, nation: str) -> list[Advice]:
    """Every legal action for `nation`, scored by its regime's weights, best first."""
    if state.phase == "crisis":
        from engine.crisis import crisis_advise
        return crisis_advise(state, nation)
    w = weights()
    scored = [Advice(action=a, score=_score(state, a, w)) for a in legal_actions(state, nation)]
    # Ties go to "wait": doing nothing is the default when nothing is better.
    return sorted(scored, key=lambda x: (-x.score, x.action.type != "wait", _key(x.action)))


# --- step --------------------------------------------------------------------


class _Log:
    def __init__(self, turn: int):
        self.turn, self.news, self.events = turn, [], []

    def add(self, type_: str, nation: str | None, text: str, **extra: Any) -> None:
        self.events.append(Event(turn=self.turn, type=type_, nation=nation, **extra))
        self.news.append(NewsItem(turn=self.turn, text=text))


def _name(s: State, n: str) -> str:
    return s.nations[n].name


def _bump(s: State, n: str, stat: str, delta: float) -> None:
    st = s.nations[n].stats
    setattr(st, stat, getattr(st, stat) + delta)


def _bump_rel(s: State, a: str, b: str, delta: float) -> None:
    k = relation_key(a, b)
    s.relations[k] = int(round(max(-100, min(100, s.relations.get(k, 0) + delta))))


def _set_link(s: State, kind: str, a: str, b: str, on: bool) -> None:
    s.links = [l for l in s.links if not (l.type == kind and {l.a, l.b} == {a, b})]
    if on:
        x, y = sorted((a, b))
        s.links.append(Link(type=kind, a=x, b=y))


def _apply(s: State, a: Action, w: dict, log: _Log) -> None:
    by, t = a.by, a.target
    if a.type == "wait" or t is None:
        return
    if a.type == "set_tariff":
        pct, tw = a.params["pct"], w["tariff"]
        _bump(s, t, "gdp", -tw["gdp_cost_target_per_pct"] * pct)
        _bump(s, by, "gdp", -tw["gdp_cost_self_per_pct"] * pct)
        _bump_rel(s, by, t, tw["relation_per_pct"] * pct)
        broke = pct >= tw["breaks_trade_at_pct"] and has_link(s, "trade", by, t)
        if broke:
            _set_link(s, "trade", by, t, False)
        log.add("tariff", by, f"{_name(s, by)} slaps a {pct}% tariff on {_name(s, t)}"
                + ("; their trade deal collapses" if broke else ""), target=t, pct=pct)
    elif a.type == "propose_trade":
        if accepts(s, a, w):
            for res, amt in a.params["give"].items():
                _bump(s, by, res, -amt); _bump(s, t, res, amt)
            for res, amt in a.params["get"].items():
                _bump(s, by, res, amt); _bump(s, t, res, -amt)
            _set_link(s, "trade", by, t, True)
            _bump_rel(s, by, t, w["trade"]["relation"])
            log.add("trade_deal", by, f"{_name(s, by)} and {_name(s, t)} sign a trade deal", target=t)
        else:
            log.add("trade_rejected", t, f"{_name(s, t)} rejects {_name(s, by)}'s trade offer", target=by)
    elif a.type == "propose_alliance":
        if accepts(s, a, w):
            _set_link(s, "alliance", by, t, True)
            _bump_rel(s, by, t, w["alliance"]["relation"])
            log.add("alliance", by, f"{_name(s, by)} and {_name(s, t)} form an alliance", target=t)
        else:
            log.add("alliance_rejected", t, f"{_name(s, t)} turns down an alliance with {_name(s, by)}", target=by)
    elif a.type == "declare_war":
        _set_link(s, "war", by, t, True)
        _set_link(s, "trade", by, t, False)
        _bump_rel(s, by, t, w["war"]["relation"])
        log.add("war", by, f"{_name(s, by)} declares war on {_name(s, t)}", target=t)
    elif a.type == "make_peace":
        _set_link(s, "war", by, t, False)
        _bump_rel(s, by, t, w["peace"]["relation"])
        log.add("peace", by, f"{_name(s, by)} and {_name(s, t)} make peace", target=t)


def _fight(s: State, rng: random.Random, w: dict, log: _Log) -> None:
    wr = w["war"]
    nb = world()["neighbours"]
    for link in sorted([l for l in s.links if l.type == "war"], key=lambda l: (l.a, l.b)):
        a, b = link.a, link.b
        pa = power(s, a, w) + rng.gauss(0, wr["noise"])
        pb = power(s, b, w) + rng.gauss(0, wr["noise"])
        winner, loser = (a, b) if pa >= pb else (b, a)
        for n in (a, b):
            _bump(s, n, "army", wr["monthly_army"])
            _bump(s, n, "gdp", wr["monthly_gdp"])
            _bump(s, n, "stability", wr["monthly_stability"])
            if s.nations[n].system == "democracy":
                _bump(s, n, "approval", wr["monthly_approval_democracy"])
        front = sorted(p for p, owner in s.provinces.items() if owner == loser
                       and any(s.provinces.get(q) == winner for q in nb[p]))
        lost_count = sum(1 for o in s.provinces.values() if o == loser)
        if front and lost_count > 1:
            p = rng.choice(front)
            s.provinces[p] = winner
            plunder = min(wr["plunder"], s.nations[loser].stats.food)
            _bump(s, loser, "food", -plunder); _bump(s, winner, "food", plunder)
            log.add("province_taken", winner, f"{_name(s, winner)} seizes a province from {_name(s, loser)}",
                    target=loser, province=p)
        if lost_count <= 2:
            _set_link(s, "war", a, b, False)
            log.add("peace", loser, f"{_name(s, loser)} sues for peace with {_name(s, winner)}", target=winner)


def _monthly(s: State, rng: random.Random, w: dict, log: _Log) -> None:
    mo = w["monthly"]
    for l in s.links:
        if l.type == "trade":
            for n in (l.a, l.b):
                _bump(s, n, "gdp", w["trade"]["monthly_gdp"])
                _bump(s, n, "food", w["trade"]["monthly_supply"])
                _bump(s, n, "oil", w["trade"]["monthly_supply"])
    base = world()["nations"]
    for n in NATION_IDS:
        st = s.nations[n].stats
        for stat in mo["revert_stats"]:  # each stat drifts back toward the nation's starting value
            _bump(s, n, stat, mo["revert_rate"] * (base[n]["stats"][stat] - getattr(st, stat)))
        if st.food < mo["food_low"]:
            _bump(s, n, "stability", mo["food_low_stability"])
        elif st.food > mo["food_high"]:
            _bump(s, n, "stability", mo["food_high_stability"])
        if st.oil < mo["oil_low"]:
            _bump(s, n, "gdp", mo["oil_low_gdp"])
    for k in sorted(s.relations):
        v = s.relations[k]
        s.relations[k] = v - mo["relation_drift"] if v > 0 else v + mo["relation_drift"] if v < 0 else 0

    ev = w["events"]
    if rng.random() < ev["chance_per_month"]:
        table = ev["table"]
        e = rng.choices(table, weights=[x["weight"] for x in table])[0]
        n = rng.choice(NATION_IDS)
        for stat, d in e["stats"].items():
            _bump(s, n, stat, d)
        log.add(e["type"], n, e["text"].format(name=_name(s, n)))


def _politics(s: State, rng: random.Random, w: dict, log: _Log) -> None:
    po = w["politics"]
    for n in NATION_IDS:
        nat = s.nations[n]
        if (nat.system == "democracy" and s.turn % po["election_every_months"] == 0
                and nat.stats.approval < po["election_min_approval"]):
            old, nat.leader = nat.leader, f"{po['titles']['democracy']} {rng.choice(po['successor_names'])}"
            nat.stats.approval = 55
            log.add("election", n, f"{old} loses the election in {nat.name}; {nat.leader} takes office")
        if nat.system == "junta" and nat.stats.stability < po["coup_below_stability"]:
            old, nat.leader = nat.leader, f"{po['titles']['junta']} {rng.choice(po['successor_names'])}"
            nat.stats.stability = po["coup_stability_after"]
            log.add("coup", n, f"Coup in {nat.name}: {old} is ousted by {nat.leader}")


def _refresh_status(s: State, w: dict) -> None:
    for n in NATION_IDS:
        nat, st = s.nations[n], s.nations[n].stats
        for stat in STAT_NAMES:
            setattr(st, stat, round(max(0.0, min(100.0, getattr(st, stat))), 1))
        st.territory = sum(1 for o in s.provinces.values() if o == n)
        nat.status = (["PROTESTS"] if st.stability < w["monthly"]["protests_below_stability"] else []) \
            + (["WAR"] if any(l.type == "war" and n in (l.a, l.b) for l in s.links) else [])


def step(state: State, actions: list[Action], seed: int) -> State:
    """Advance one month. Pure: the input state is not modified."""
    if state.phase == "crisis":
        from engine.crisis import crisis_step
        return crisis_step(state, actions, seed)
    s = state.model_copy(deep=True)
    if s.phase != "strategy":
        return s  # the game has ended
    w = weights()
    rng = random.Random(f"{seed}:{s.turn}")
    s.turn += 1
    log = _Log(s.turn)

    seen = set()
    for a in sorted(actions, key=lambda a: (a.by, _key(a))):
        if a.by in seen or not is_legal(s, a):
            continue  # one action per nation per month; the turn loop replaces illegal ones
        seen.add(a.by)
        _apply(s, a, w, log)
    start = {n: s.nations[n].stats.model_copy() for n in NATION_IDS}
    _fight(s, rng, w, log)
    _monthly(s, rng, w, log)
    mo = w["monthly"]
    for n in NATION_IDS:
        st, st0 = s.nations[n].stats, start[n]
        _bump(s, n, "approval", mo["approval_per_gdp"] * (st.gdp - st0.gdp)
              + mo["approval_per_stability"] * (st.stability - st0.stability))
    _politics(s, rng, w, log)
    _refresh_status(s, w)

    s.news = (s.news + log.news)[-KEEP_NEWS:]
    s.events = (s.events + log.events)[-KEEP_NEWS:]
    return s
