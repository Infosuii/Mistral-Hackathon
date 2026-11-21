"""Crisis mode, pure like engine.core: start_crisis and crisis_step return new States.

One tick of crisis_step, in order:
  1. tick + 1; yesterday's incoming call is cleared.
  2. `announce` actions become public commitments (a leader who was not interrupted).
  3. Explicit decisions are recorded (a leader's choice, or a deal from a call).
  4. Any nation at its deadline without a decision takes its advisers' top.
  5. Scripted events for this tick: incoming_call, compare_notes, forecast.
  6. At the last tick, the crisis resolves and the world goes back to strategy.
Numbers live in the crisis file's "rules" (data/crises/<id>.json).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from contracts.models import (
    NATION_IDS, Action, Advice, Crisis, CrisisFile, Decision, Event, IncomingCall, NewsItem,
    PublicCommitment, State, relation_key,
)

CRISES = Path(__file__).resolve().parent.parent / "data" / "crises"


@lru_cache(maxsize=None)
def _raw(crisis_id: str) -> str:
    return (CRISES / f"{crisis_id}.json").read_text()


def crisis_file(crisis_id: str) -> CrisisFile:
    return CrisisFile.model_validate(json.loads(_raw(crisis_id)))


def available() -> list[str]:
    return sorted(p.stem for p in CRISES.glob("*.json"))


def _rules(s: State) -> dict[str, Any]:
    return crisis_file(s.crisis.id).rules


def _say(s: State, text: str, type_: str, nation: str | None = None, **extra: Any) -> None:
    turn = s.turn
    s.news.append(NewsItem(turn=turn, text=text))
    s.events.append(Event(turn=turn, type=type_, nation=nation, **extra))


# --- start -------------------------------------------------------------------


def start_crisis(state: State, crisis_id: str) -> State:
    cf = crisis_file(crisis_id)
    s = state.model_copy(deep=True)
    s.phase = "crisis"
    s.crisis = Crisis(id=cf.id, tick=0, ticks_total=cf.ticks_total, deadlines=cf.deadlines)
    s.incoming_call = None
    _say(s, cf.intro_news, "crisis_start", None, crisis=cf.id)
    return s


# --- legal actions and advice ------------------------------------------------


def crisis_legal(s: State, nation: str) -> list[Action]:
    c = s.crisis
    if nation in c.decisions or c.tick > c.deadlines.get(nation, c.ticks_total):
        return []
    return [Action(type=a, by=nation) for a in crisis_file(c.id).actions.get(nation, [])]


def _player_promises(s: State, to: str) -> list:
    return [p for p in s.crisis.promises if p.by == "player" and p.to == to and p.kept is not False]


def berth_belief(s: State, nation: str) -> float:
    """How sure `nation` is that it will get the berth."""
    c, r = s.crisis, _rules(s)
    tugs = r["second_berth_requires"]
    t = c.decisions.get(tugs["nation"])
    if t and t.action == tugs["action"] and t.tick <= tugs["by_tick"]:
        return 1.0
    k = c.decisions.get("kessaria")
    if k:
        if k.action == f"assign_berth_{nation}":
            return 1.0
        if k.action == "split_day":
            return r["split_day_belief"]
        return 0.0
    belief = r["berth_prior"]
    b = s.nations[nation].beliefs
    trust = b.trust_in_player if b else 0.5
    for p in _player_promises(s, nation):
        if p.what == "berth":
            belief += r["promise_weight"] * trust
    return min(1.0, belief)


def _score(s: State, nation: str, action: str) -> float:
    r = _rules(s)
    pay = r["payoffs"].get(nation, {}).get(action, {})
    nat = s.nations[nation]
    b = nat.beliefs
    score = pay.get("base", 0.0)
    score += pay.get("berth", 0.0) * berth_belief(s, nation)
    score += pay.get("low_resolve", 0.0) * (1 - (b.resolve_of_player if b else 0.5))
    trust = b.trust_in_player if b else 0.5
    score += sum(r["promise_bonus"] * trust for p in _player_promises(s, nation) if p.what == action)
    committed = [pc.action for pc in s.crisis.public_commitments if pc.nation == nation]
    if committed and action not in committed:
        score -= r["public_backdown_cost"].get(nat.system, 0)
    return round(score, 2)


def crisis_advise(s: State, nation: str) -> list[Advice]:
    ranked = [Advice(action=a, score=_score(s, nation, a.type)) for a in crisis_legal(s, nation)]
    return sorted(ranked, key=lambda x: (-x.score, x.action.type))


# --- one tick ------------------------------------------------------------------


def _decide(s: State, nation: str, action: str) -> None:
    s.crisis.decisions[nation] = Decision(action=action, tick=s.crisis.tick)
    _say(s, f"{s.nations[nation].name} decides: {action.replace('_', ' ')}", "crisis_decision", nation, action=action)


def _compatible(r: dict, a: str, b: str) -> bool:
    return any({a, b} == set(pair) for pair in r["compatible_when"])


def _compare_notes(s: State, between: list[str]) -> None:
    r = _rules(s)
    a, b = between
    clash = [(p, q) for p in _player_promises(s, a) for q in _player_promises(s, b)
             if p.what == q.what and p.condition is None and q.condition is None
             and not _compatible(r, p.when, q.when)]
    if not clash:
        _say(s, f"{s.nations[a].name} and {s.nations[b].name} compare notes; your story holds",
             "compare_notes", a, target=b, contradiction=False)
        return
    for n in (a, b):
        bl = s.nations[n].beliefs
        if bl:
            bl.trust_in_player = round(bl.trust_in_player * r["contradiction_trust_factor"], 3)
    for p, q in clash:
        p.kept = q.kept = False
    _say(s, f"{s.nations[a].name} and {s.nations[b].name} compare notes: you promised the {clash[0][0].what} to both",
         "compare_notes", a, target=b, contradiction=True)


def _scripted(s: State, cf: CrisisFile) -> None:
    for e in cf.scripted:
        if e.tick != s.crisis.tick:
            continue
        if e.type == "incoming_call":
            s.incoming_call = IncomingCall(**{"from": e.from_, "emotion": e.emotion,
                                              "opening_line": e.opening_line})
            _say(s, f"{s.nations[e.from_].leader} is on the line", "incoming_call", e.from_)
        elif e.type == "compare_notes":
            _compare_notes(s, e.between)
        elif e.type == "forecast":
            _say(s, e.text, "forecast")


def _bump(s: State, n: str, stat: str, d: float) -> None:
    st = s.nations[n].stats
    setattr(st, stat, round(max(0.0, min(100.0, getattr(st, stat) + d)), 1))


def _rel(s: State, key: str, d: float) -> None:
    s.relations[key] = int(max(-100, min(100, s.relations.get(key, 0) + d)))


def berth_holders(s: State) -> dict[str, str]:
    """Who docked: nation -> 'berth' or 'half_berth'."""
    c, r = s.crisis, _rules(s)
    dec = {n: d.action for n, d in c.decisions.items()}
    if dec.get("kessaria") == "close_port":
        return {}
    blocked = r["outcomes"]["blockade"]["blocks"] if dec.get("ostrava") == "blockade" else None
    docking = [n for n in r["needs_berth"] if dec.get(n) == "dock" and n != blocked]
    tugs = r["second_berth_requires"]
    t = c.decisions.get(tugs["nation"])
    if t and t.action == tugs["action"] and t.tick <= tugs["by_tick"]:
        return {n: "berth" for n in docking}
    k = dec.get("kessaria")
    if k == "split_day":
        return {n: "half_berth" if len(docking) > 1 else "berth" for n in docking}
    if k and k.startswith("assign_berth_"):
        x = k.removeprefix("assign_berth_")
        return {x: "berth"} if x in docking else {}
    return {docking[0]: "berth"} if len(docking) == 1 else {}


def _resolve(s: State) -> None:
    c, r = s.crisis, _rules(s)
    out = r["outcomes"]
    dec = {n: d.action for n, d in c.decisions.items()}
    holders = berth_holders(s)
    cf_actions = crisis_file(c.id).actions
    for n in r["needs_berth"]:
        for stat, d in out[holders.get(n, "no_berth")].items():
            _bump(s, n, stat, d)
    if dec.get("ostrava") == "blockade":
        _bump(s, "kessaria", "gdp", out["blockade"]["kessaria_gdp"])
        for k, d in out["blockade"]["relations"].items():
            _rel(s, k, d)
    if dec.get("zarnia") == "mobilise":
        for k, d in out["mobilise"]["relations"].items():
            _rel(s, k, d)
    war = (out["blockade_and_mobilise_means_war"] and dec.get("ostrava") == "blockade"
           and dec.get("zarnia") == "mobilise")
    if war and not any(l.type == "war" and {l.a, l.b} == {"ostrava", "zarnia"} for l in s.links):
        from contracts.models import Link
        s.links.append(Link(type="war", a="ostrava", b="zarnia"))
    if dec.get("kessaria") == "close_port":
        _bump(s, "kessaria", "gdp", out["close_port"]["kessaria_gdp"])
    v = dec.get("valdoria", "")
    if v.startswith("favour_"):
        fav = v.removeprefix("favour_")
        other = next(n for n in r["needs_berth"] if n != fav)
        _rel(s, relation_key("valdoria", fav), out["favour"]["favoured_relation"])
        _rel(s, relation_key("valdoria", other), out["favour"]["other_relation"])
    elif v == "split_cargo":
        for n in r["needs_berth"]:
            _bump(s, n, "food", out["split_cargo"]["food"])

    for p in c.promises:
        if p.by != "player":
            continue
        if p.kept is None:
            if p.what == "berth":
                p.kept = p.to in holders
            elif p.what in cf_actions.get(p.to, []):
                p.kept = dec.get(p.to) == p.what
        b = s.nations[p.to].beliefs
        if b and p.kept is not None:
            d = r["kept_trust"] if p.kept else r["broken_trust"]
            b.trust_in_player = round(min(1.0, max(0.0, b.trust_in_player + d)), 3)

    docked = ", ".join(f"{s.nations[n].name} ({h.replace('_', ' ')})" for n, h in holders.items()) or "nobody"
    _say(s, f"{crisis_file(c.id).title} is over. Docked: {docked}." + (" Ostrava and Zarnia are at war." if war else ""),
         "crisis_resolved", None, crisis=c.id, decisions=dec, holders=holders, war=war)
    for n in NATION_IDS:
        st = s.nations[n].stats
        st.territory = sum(1 for o in s.provinces.values() if o == n)
    s.phase, s.crisis, s.incoming_call = "strategy", None, None


def crisis_step(state: State, actions: list[Action], seed: int) -> State:
    """Advance one crisis tick. Pure. `actions` may hold decisions (a type from the
    crisis file) and `announce` actions ({"type": "announce", "by": n, "params": {"action": a}})."""
    s = state.model_copy(deep=True)
    c = s.crisis
    cf = crisis_file(c.id)
    c.tick += 1
    s.incoming_call = None

    for a in sorted((a for a in actions if a.type == "announce"), key=lambda a: a.by):
        act = a.params.get("action")
        if act and not any(pc.nation == a.by and pc.action == act for pc in c.public_commitments):
            c.public_commitments.append(PublicCommitment(nation=a.by, action=act, tick=c.tick))
            _say(s, f"{s.nations[a.by].name} publicly announces: {act}", "public_commitment", a.by, action=act)

    for a in sorted((a for a in actions if a.type != "announce"), key=lambda a: (a.by, a.type)):
        if any(x.type == a.type for x in crisis_legal(s, a.by)):
            _decide(s, a.by, a.type)

    for n in NATION_IDS:
        if n not in c.decisions and c.deadlines.get(n) == c.tick:
            top = crisis_advise(s, n)
            if top:
                _decide(s, n, top[0].action.type)

    _scripted(s, cf)
    if c.tick >= c.ticks_total:
        for n in NATION_IDS:  # anyone without a decision by the end takes their advisers' top
            if n not in c.decisions:
                top = crisis_advise(s, n)
                if top:
                    _decide(s, n, top[0].action.type)
        _resolve(s)
    s.news, s.events = s.news[-30:], s.events[-30:]
    return s
