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
def crisis_file(crisis_id: str) -> CrisisFile:
    """Parsed data/crises/<id>.json. Shared and read-only: never modify what this returns."""
    return CrisisFile.model_validate(json.loads((CRISES / f"{crisis_id}.json").read_text()))


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
    """Live promises from the player to `to`, counting only those made before this tick."""
    return [p for p in s.crisis.promises if p.by == "player" and p.to == to
            and p.kept is not False and p.tick <= s.crisis.tick]


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
    if "berth" in pay:
        score += pay["berth"] * berth_belief(s, nation)
    score += pay.get("low_resolve", 0.0) * (1 - (b.resolve_of_player if b else 0.5))
    trust = b.trust_in_player if b else 0.5
    score += sum(r.get("promise_bonus", 4) * trust for p in _player_promises(s, nation) if p.what == action)
    committed = [pc.action for pc in s.crisis.public_commitments if pc.nation == nation]
    if committed and action not in committed:
        score -= r.get("public_backdown_cost", {}).get(nat.system, 0)
    return round(score, 2)


def crisis_advise(s: State, nation: str) -> list[Advice]:
    ranked = [Advice(action=a, score=_score(s, nation, a.type)) for a in crisis_legal(s, nation)]
    return sorted(ranked, key=lambda x: (-x.score, x.action.type))


# --- one tick ------------------------------------------------------------------


def _decide(s: State, nation: str, action: str) -> None:
    s.crisis.decisions[nation] = Decision(action=action, tick=s.crisis.tick)
    _say(s, f"{s.nations[nation].name} decides: {action.replace('_', ' ')}", "crisis_decision", nation, action=action)


def _compatible(r: dict, a: str, b: str) -> bool:
    return any({a, b} == set(pair) for pair in r.get("compatible_when", []))


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
            bl.trust_in_player = round(bl.trust_in_player * r.get("contradiction_trust_factor", 0.4), 3)
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


def _war(s: State, a: str, b: str) -> bool:
    """Start a war between a and b; False if they were already at war."""
    if any(l.type == "war" and {l.a, l.b} == {a, b} for l in s.links):
        return False
    from contracts.models import Link
    x, y = sorted((a, b))
    s.links.append(Link(type="war", a=x, b=y))
    return True


def _one_berth_outcomes(s: State, dec: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """One Berth's own resolver: who docks, and what the blockade and mobilisation cost."""
    r = _rules(s)
    out = r["outcomes"]
    holders = berth_holders(s)
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
    notes = []
    if (out["blockade_and_mobilise_means_war"] and dec.get("ostrava") == "blockade"
            and dec.get("zarnia") == "mobilise"):
        _war(s, "ostrava", "zarnia")
        notes.append("Ostrava and Zarnia are at war.")
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
    docked = ", ".join(f"{s.nations[n].name} ({h.replace('_', ' ')})" for n, h in holders.items()) or "nobody"
    return holders, [f"Docked: {docked}."] + notes


def _matches(when: dict, dec: dict[str, str]) -> bool:
    return all(dec.get(n) in (v if isinstance(v, list) else [v]) for n, v in when.items())


def _rule_outcomes(s: State, dec: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Generic resolver: every rule in rules.outcomes whose `when` matches the decisions fires.

    {"when": {"zarnia": "mobilise", "kessaria": ["close_port", "split_day"]},
     "effects": {"stats": {"zarnia": {"stability": -5}}, "relations": {"kessaria|zarnia": -10},
                 "war": ["kessaria", "zarnia"], "peace": ["a", "b"], "news": "Shots on the border."}}
    A `when` value is one action or a list of allowed actions; {} always fires."""
    notes = []
    for rule in _rules(s).get("outcomes", []):
        if not _matches(rule.get("when", {}), dec):
            continue
        eff = rule.get("effects", {})
        for n, stats in eff.get("stats", {}).items():
            for stat, d in stats.items():
                _bump(s, n, stat, d)
        for k, d in eff.get("relations", {}).items():
            _rel(s, k, d)
        if eff.get("war"):
            _war(s, *eff["war"])
        if eff.get("peace"):
            pair = set(eff["peace"])
            s.links = [l for l in s.links if not (l.type == "war" and {l.a, l.b} == pair)]
        if eff.get("news"):
            notes.append(eff["news"])
    return {}, notes


def _resolve(s: State) -> None:
    c, r = s.crisis, _rules(s)
    dec = {n: d.action for n, d in c.decisions.items()}
    cf_actions = crisis_file(c.id).actions
    wars_before = {frozenset((l.a, l.b)) for l in s.links if l.type == "war"}
    if r.get("resolver") == "one_berth":
        holders, notes = _one_berth_outcomes(s, dec)
    else:
        holders, notes = _rule_outcomes(s, dec)
    war = any(frozenset((l.a, l.b)) not in wars_before for l in s.links if l.type == "war")

    for p in c.promises:
        if p.by != "player":
            continue
        if p.kept is None:
            if p.what == "berth" and r.get("resolver") == "one_berth":
                p.kept = p.to in holders
            elif p.what in cf_actions.get(p.to, []):
                p.kept = dec.get(p.to) == p.what
        b = s.nations[p.to].beliefs
        if b and p.kept is not None:
            d = r.get("kept_trust", 0.15) if p.kept else r.get("broken_trust", -0.2)
            b.trust_in_player = round(min(1.0, max(0.0, b.trust_in_player + d)), 3)

    _say(s, " ".join([f"{crisis_file(c.id).title} is over."] + notes),
         "crisis_resolved", None, crisis=c.id, decisions=dec, holders=holders, war=war,
         promises_kept=sum(1 for p in c.promises if p.by == "player" and p.kept is True),
         promises_broken=sum(1 for p in c.promises if p.by == "player" and p.kept is False))
    for n in NATION_IDS:
        st = s.nations[n].stats
        st.territory = sum(1 for o in s.provinces.values() if o == n)
    s.phase, s.crisis, s.incoming_call = "strategy", None, None


def crisis_step(state: State, actions: list[Action], seed: int) -> State:
    """Advance one crisis tick. Pure. `actions` may hold decisions (a type from the
    crisis file) and `announce` actions ({"type": "announce", "by": n, "params": {"action": a}})."""
    from engine.core import copy_state
    s = copy_state(state)
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


# --- rerun (for the replay) --------------------------------------------------------


def _scores(advice: list[Advice]) -> dict[str, float]:
    return {a.action.type: a.score for a in advice}


def rerun_crisis(start: State, calls: list, cached: dict[str, Decision],
                 cached_advice: dict[str, list[Advice]], announces: list[tuple[int, Action]],
                 seed: int) -> tuple[State, dict[str, str]]:
    """Play a crisis again from its first state, with the player's calls at new ticks.

    `calls` is [(tick, to, CallOutput, interrupted)]; a call at tick t happens after the
    world reaches t, as in the live game. A leader whose advice comes out the same as it
    did originally keeps its cached decision; one whose advice changed takes its
    advisers' new top. Pure, no model calls. Returns the final state and every decision."""
    from engine.calls import apply_call_effects

    s = start.model_copy(deep=True)
    queued: list[Action] = []

    def take_calls(state: State, tick: int) -> State:
        for t, to, out, interrupted in calls:
            if t == tick:
                state, _ = apply_call_effects(state, to, out, interrupted)
                queued.extend(out.actions)
        return state

    s = take_calls(s, 0)
    while s.phase == "crisis":
        nxt = s.crisis.tick + 1
        actions = [a for t, a in announces if t == nxt] + queued
        queued_by = {a.by for a in queued}
        queued.clear()
        for n, d in cached.items():
            if n not in cached_advice or d.tick != nxt or n in s.crisis.decisions or n in queued_by:
                continue
            now = crisis_advise(s, n)
            if now and _scores(now) != _scores(cached_advice[n]):
                actions.append(now[0].action)  # inputs changed: follow the advisers
            else:
                actions.append(Action(type=d.action, by=n))
        s = crisis_step(s, actions, seed)
        if s.crisis:
            s = take_calls(s, s.crisis.tick)
    resolved = next(e for e in reversed(s.events) if e.type == "crisis_resolved")
    return s, dict(resolved.model_extra["decisions"])
