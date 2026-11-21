"""Province-level war for GAMBIT (behind GAMBIT_WAR=1).

Troops sit in provinces. A nation's army stat becomes troops spread over its provinces
(more at the capital and on borders). An attack sends troops from your strongest
province next to the target; each hop between provinces takes a few seconds. When they
arrive, firepower in that province decides it: attackers against the garrison, with a
defence bonus at the capital. Winners take the province and, unless told to stop, keep
advancing into the weakest neighbouring enemy province. AI leaders recruit, attack and
declare war on you when relations are bad enough; they answer peace offers, tribute and
non-aggression pacts from the war score.

Time is real time (time.monotonic, injectable for tests): the page polls GET /war and
everything due by "now" is resolved in order. Province changes go into GAME.state
(provinces, territory, links, relations, news), so the map, the engine and the leaders
see them.
"""
from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from contracts.models import NewsItem, State, relation_key

ROOT = Path(__file__).resolve().parent.parent
MAP = json.loads((ROOT / "web" / "src" / "map.json").read_text())
NEIGHBOURS: dict[str, list[str]] = json.loads((ROOT / "data" / "nations.json").read_text())["neighbours"]
CENTERS: dict[str, tuple[float, float]] = {p["id"]: tuple(p["center"]) for p in MAP["provinces"]}

TROOPS_PER_ARMY = 100       # army stat 85 -> 8,500 troops
HOP_SECONDS = 3.0           # base time to march between neighbouring provinces
HOP_PER_PX = 1 / 40         # plus a second per 40 map px
CAPITAL_DEFENCE = 1.35
DUG_IN = 1.1                # any garrison defends a little better than it attacks
SEND_SHARE = 0.7            # share of the source garrison that marches
LEAVE_BEHIND = 0.3          # share an advancing army leaves in each captured province
MIN_ADVANCE = 300           # an army smaller than this stops advancing
RECRUIT_COST_GDP = 1.0      # economy points per 100 troops
RECRUIT_SECONDS = 5.0
AI_THINK_SECONDS = 6.0
AI_DECLARE_RELATION = -50   # an AI leader this hostile, and strong enough, declares war on you
AI_DECLARE_SECONDS = 20.0
PACT_SECONDS = 180.0


def _capital_province(nation: str) -> Optional[str]:
    c = MAP["capitals"].get(nation)
    if not c:
        return None
    return min(CENTERS, key=lambda p: math.dist(CENTERS[p], c))


CAPITALS = {n: _capital_province(n) for n in MAP["capitals"]}


def hop_seconds(a: str, b: str) -> float:
    return round(HOP_SECONDS + math.dist(CENTERS[a], CENTERS[b]) * HOP_PER_PX, 2)


@dataclass
class Army:
    id: int
    owner: str
    src: str
    dst: str
    troops: float
    depart: float
    arrive: float
    advance: bool = True   # keep going after a win
    target: Optional[str] = None  # the enemy this army is fighting


@dataclass
class War:
    a: str
    b: str
    started_turn: int
    started_at: float
    taken: dict[str, int] = field(default_factory=dict)    # provinces captured by each side
    lost: dict[str, float] = field(default_factory=dict)   # troops lost by each side
    battles: int = 0

    def score(self, n: str) -> float:
        """Provinces taken count most; troop losses break ties."""
        other = self.b if n == self.a else self.a
        return round(self.taken.get(n, 0) * 10 + (self.lost.get(other, 0) - self.lost.get(n, 0)) / 500, 1)


class WarRoom:
    """All war state for one game. Rebuilt when the game restarts (GAME.epoch changes)."""

    def __init__(self, state: State, clock: Callable[[], float] = time.monotonic, seed: int = 7):
        self.clock = clock
        self.rng = random.Random(seed)
        self.garrison: dict[str, float] = {}
        self.armies: list[Army] = []
        self.wars: dict[str, War] = {}
        self.log: list[dict[str, Any]] = []
        self.pacts: dict[str, float] = {}           # relation key -> expires at
        self.recruits: list[tuple[float, str, float]] = []  # (ready_at, nation, troops)
        self.next_ai: dict[str, float] = {}
        self.next_declare = clock() + AI_DECLARE_SECONDS
        self.seq = 0
        self.army_seen: dict[str, float] = {}
        self._deploy(state)

    # --- setup and sync ------------------------------------------------------

    def _deploy(self, state: State) -> None:
        for nation, n in state.nations.items():
            owned = [p for p, o in state.provinces.items() if o == nation]
            if not owned:
                continue
            weights = {}
            for p in owned:
                border = any(state.provinces.get(q) not in (None, nation) for q in NEIGHBOURS.get(p, []))
                weights[p] = 2.0 if p == CAPITALS.get(nation) else 1.5 if border else 1.0
            total = n.stats.army * TROOPS_PER_ARMY
            wsum = sum(weights.values())
            for p in owned:
                self.garrison[p] = round(total * weights[p] / wsum)
            self.army_seen[nation] = n.stats.army

    def troops(self, nation: str, state: State) -> float:
        held = sum(t for p, t in self.garrison.items() if state.provinces.get(p) == nation)
        return held + sum(a.troops for a in self.armies if a.owner == nation)

    def _sync(self, state: State) -> None:
        """Follow changes the engine made on its own (monthly war rolls, army drift)."""
        for nation, n in state.nations.items():
            seen = self.army_seen.get(nation)
            if seen and abs(n.stats.army - seen) > 0.5:
                factor = max(0.1, n.stats.army / seen)
                for p, o in state.provinces.items():
                    if o == nation:
                        self.garrison[p] = round(self.garrison.get(p, 0) * factor)
            self.army_seen[nation] = n.stats.army

    def _write_army(self, state: State, nation: str) -> None:
        army = round(self.troops(nation, state) / TROOPS_PER_ARMY, 1)
        state.nations[nation].stats.army = army
        self.army_seen[nation] = army

    # --- helpers -----------------------------------------------------------------

    def at_war(self, a: str, b: str) -> bool:
        return relation_key(a, b) in self.wars

    def enemies(self, nation: str) -> list[str]:
        return [w.b if w.a == nation else w.a for w in self.wars.values() if nation in (w.a, w.b)]

    def _note(self, state: State, kind: str, text: str, **extra: Any) -> None:
        entry = {"t": round(self.clock(), 2), "turn": state.turn, "kind": kind, "text": text, **extra}
        self.log.append(entry)
        state.news.append(NewsItem(turn=state.turn, text=text))
        state.news[:] = state.news[-40:]

    def _name(self, state: State, n: str) -> str:
        return state.nations[n].name if n in state.nations else n.title()

    # --- player and AI orders ----------------------------------------------------

    def declare(self, state: State, by: str, target: str) -> str:
        if by == target or target not in state.nations:
            raise ValueError("choose another nation")
        key = relation_key(by, target)
        if key in self.wars:
            raise ValueError(f"already at war with {self._name(state, target)}")
        if self.pacts.get(key, 0) > self.clock() and by == state.seat.nation:
            self.pacts.pop(key)  # breaking a pact costs extra trust below
            b = state.nations[target].beliefs
            if b:
                b.trust_in_player = round(max(0.0, b.trust_in_player - 0.3), 3)
        self.wars[key] = War(a=by, b=target, started_turn=state.turn, started_at=self.clock())
        if not any(l.type == "war" and {l.a, l.b} == {by, target} for l in state.links):
            from contracts.models import Link
            state.links.append(Link(type="war", a=by, b=target))
        state.relations[key] = max(-100, state.relations.get(key, 0) - 40)
        for n in (by, target):
            if "WAR" not in state.nations[n].status:
                state.nations[n].status.append("WAR")
        self.next_ai.setdefault(target, self.clock() + 2.0)
        text = f"{self._name(state, by)} declares war on {self._name(state, target)}"
        self._note(state, "declare", text, attacker=by, defender=target)
        return text

    def attack(self, state: State, by: str, province: str, share: float = SEND_SHARE,
               advance: bool = True, src: Optional[str] = None) -> Army:
        owner = state.provinces.get(province)
        if owner is None:
            raise ValueError("no such province")
        if owner == by:
            raise ValueError("that province is already yours")
        if not self.at_war(by, owner):
            raise ValueError(f"declare war on {self._name(state, owner)} first")
        sources = [q for q in NEIGHBOURS.get(province, []) if state.provinces.get(q) == by]
        if src is not None:
            sources = [src] if src in sources else []
        if not sources:
            raise ValueError("that province is not on your border: take the provinces in between first")
        src = max(sources, key=lambda q: self.garrison.get(q, 0))
        troops = round(self.garrison.get(src, 0) * max(0.1, min(1.0, share)))
        if troops < 50:
            raise ValueError("not enough troops next to that province: recruit or move more in")
        self.garrison[src] -= troops
        now = self.clock()
        self.seq += 1
        army = Army(id=self.seq, owner=by, src=src, dst=province, troops=troops, depart=now,
                    arrive=now + hop_seconds(src, province), advance=advance, target=owner)
        self.armies.append(army)
        self._note(state, "march", f"{self._name(state, by)} sends {troops:,.0f} troops from "
                   f"{src.upper()} toward {province.upper()} ({self._name(state, owner)})",
                   attacker=by, defender=owner, province=province)
        return army

    def recruit(self, state: State, nation: str, troops: float) -> float:
        troops = max(100.0, min(3000.0, float(troops)))
        cost = troops / 100 * RECRUIT_COST_GDP
        stats = state.nations[nation].stats
        if stats.gdp - cost < 5:
            raise ValueError(f"not enough economy: {troops:,.0f} troops cost {cost:.0f} economy")
        stats.gdp = round(stats.gdp - cost, 1)
        ready = self.clock() + RECRUIT_SECONDS
        self.recruits.append((ready, nation, troops))
        self._note(state, "recruit", f"{self._name(state, nation)} raises {troops:,.0f} troops "
                   f"(ready in {RECRUIT_SECONDS:.0f} s)", attacker=nation)
        return cost

    def peace(self, state: State, by: str, target: str, kind: str, amount: float = 0) -> dict[str, Any]:
        """kind: white (no terms), pay (you pay tribute), demand (they pay tribute), pact."""
        key = relation_key(by, target)
        name = self._name(state, target)
        if kind == "pact":
            if key in self.wars:
                return {"accepted": False, "reply": f"{name} will not sign a pact in the middle of a war."}
            rel = state.relations.get(key, 0)
            ok = rel >= -10
            if ok:
                self.pacts[key] = self.clock() + PACT_SECONDS
                state.relations[key] = min(100, rel + 10)
                self._note(state, "pact", f"{self._name(state, by)} and {name} sign a non-aggression pact")
            return {"accepted": ok, "reply": (f"{name} signs a non-aggression pact." if ok else
                                              f"{name} refuses: relations are too poor ({rel}).")}
        war = self.wars.get(key)
        if not war:
            return {"accepted": False, "reply": f"You are not at war with {name}."}
        mine, theirs = war.score(by), war.score(target)
        ahead = theirs - mine  # how far the other side is winning
        amount = max(0.0, float(amount))
        if kind == "white":
            ok = ahead <= 5
            reply = (f"{name} accepts peace without terms." if ok else
                     f"{name} is winning ({theirs:.0f} to {mine:.0f}) and wants tribute.")
        elif kind == "pay":
            need = max(5.0, ahead * 1.5)
            ok = amount >= need and state.nations[by].stats.gdp - amount >= 5
            reply = (f"{name} takes {amount:.0f} economy in tribute and ends the war." if ok else
                     f"{name} wants at least {need:.0f} economy in tribute.")
        elif kind == "demand":
            ok = mine - theirs >= 15
            amount = amount or 10
            reply = (f"{name} pays {amount:.0f} economy in tribute to end the war." if ok else
                     f"{name} refuses to pay: you are not winning by enough ({mine:.0f} to {theirs:.0f}).")
        else:
            raise ValueError("kind is white, pay, demand or pact")
        if ok:
            payer, payee = (by, target) if kind == "pay" else (target, by)
            if kind in ("pay", "demand"):
                give = min(amount, max(0.0, state.nations[payer].stats.gdp - 5))
                state.nations[payer].stats.gdp = round(state.nations[payer].stats.gdp - give, 1)
                state.nations[payee].stats.gdp = round(state.nations[payee].stats.gdp + give, 1)
            self._end_war(state, key, f"{self._name(state, by)} and {name} make peace"
                          + {"white": "", "pay": f"; {self._name(state, by)} pays tribute",
                             "demand": f"; {name} pays tribute"}[kind])
        return {"accepted": ok, "reply": reply}

    def _end_war(self, state: State, key: str, text: str) -> None:
        war = self.wars.pop(key, None)
        if not war:
            return
        state.links[:] = [l for l in state.links if not (l.type == "war" and {l.a, l.b} == {war.a, war.b})]
        # Armies marching against each other go home to their source province.
        for army in [x for x in self.armies if {x.owner, x.target} == {war.a, war.b}]:
            if state.provinces.get(army.src) == army.owner:
                self.garrison[army.src] = self.garrison.get(army.src, 0) + army.troops
            self.armies.remove(army)
        state.relations[key] = min(100, state.relations.get(key, 0) + 15)
        for n in (war.a, war.b):
            if not self.enemies(n) and "WAR" in state.nations[n].status:
                state.nations[n].status.remove("WAR")
        self._note(state, "peace", text)

    # --- the clock -----------------------------------------------------------------

    def advance(self, state: State) -> None:
        """Resolve everything due by now, in time order, then let AI leaders act."""
        self._sync(state)
        now = self.clock()
        for ready, nation, troops in sorted(r for r in self.recruits if r[0] <= now):
            cap = CAPITALS.get(nation)
            home = cap if state.provinces.get(cap) == nation else next(
                (p for p, o in state.provinces.items() if o == nation), None)
            if home:
                self.garrison[home] = self.garrison.get(home, 0) + troops
                self._write_army(state, nation)
        self.recruits = [r for r in self.recruits if r[0] > now]
        while True:
            due = sorted((a for a in self.armies if a.arrive <= now), key=lambda a: a.arrive)
            if not due:
                break
            self._arrive(state, due[0])
        self._ai(state, now)

    def _arrive(self, state: State, army: Army) -> None:
        self.armies.remove(army)
        p = army.dst
        owner = state.provinces.get(p)
        if owner == army.owner:  # reinforcement
            self.garrison[p] = self.garrison.get(p, 0) + army.troops
            return
        key = relation_key(army.owner, owner) if owner else None
        if not owner or key not in self.wars:  # peace was made on the way: go home
            if state.provinces.get(army.src) == army.owner:
                self.garrison[army.src] = self.garrison.get(army.src, 0) + army.troops
            return
        war = self.wars[key]
        war.battles += 1
        defenders = self.garrison.get(p, 0)
        mult = CAPITAL_DEFENCE if p == CAPITALS.get(owner) else DUG_IN
        attack = army.troops * self.rng.uniform(0.9, 1.1)
        defence = defenders * mult * self.rng.uniform(0.9, 1.1)
        a_name, d_name = self._name(state, army.owner), self._name(state, owner)
        if attack > defence:
            lost = min(army.troops * 0.9, defence * 0.6)
            survivors = round(army.troops - lost)
            war.lost[army.owner] = war.lost.get(army.owner, 0) + lost
            war.lost[owner] = war.lost.get(owner, 0) + defenders
            war.taken[army.owner] = war.taken.get(army.owner, 0) + 1
            self._transfer(state, p, army.owner, owner)
            self.log_battle(state, p, army.owner, owner, army.troops, defenders, army.owner,
                            f"{a_name} takes {p.upper()} from {d_name} ({army.troops:,.0f} vs {defenders:,.0f}"
                            f"{', capital' if mult == CAPITAL_DEFENCE else ''})")
            nxt = self._next_target(state, p, army.owner, owner) if army.advance else None
            if nxt and survivors >= MIN_ADVANCE:
                stay = round(survivors * LEAVE_BEHIND)
                self.garrison[p] = stay
                now = self.clock()
                self.seq += 1
                self.armies.append(Army(id=self.seq, owner=army.owner, src=p, dst=nxt, troops=survivors - stay,
                                        depart=now, arrive=now + hop_seconds(p, nxt), advance=True, target=owner))
            else:
                self.garrison[p] = survivors
            if not any(o == owner for o in state.provinces.values()):
                self._end_war(state, key, f"{d_name} is overrun; {a_name} wins the war")
        else:
            lost_d = min(defenders * 0.95, attack / mult * 0.5)
            self.garrison[p] = round(defenders - lost_d)
            war.lost[army.owner] = war.lost.get(army.owner, 0) + army.troops
            war.lost[owner] = war.lost.get(owner, 0) + lost_d
            self.log_battle(state, p, army.owner, owner, army.troops, defenders, owner,
                            f"{d_name} holds {p.upper()} against {a_name} ({defenders:,.0f} vs {army.troops:,.0f})")
        for n in (army.owner, owner):
            self._write_army(state, n)

    def log_battle(self, state: State, p: str, attacker: str, defender: str, a_troops: float,
                   d_troops: float, winner: str, text: str) -> None:
        self._note(state, "battle", text, province=p, attacker=attacker, defender=defender,
                   winner=winner, attackers=round(a_troops), defenders=round(d_troops))

    def _transfer(self, state: State, p: str, to: str, frm: str) -> None:
        state.provinces[p] = to
        for n in (to, frm):
            state.nations[n].stats.territory = sum(1 for o in state.provinces.values() if o == n)

    def _next_target(self, state: State, p: str, by: str, enemy: str) -> Optional[str]:
        options = [q for q in NEIGHBOURS.get(p, []) if state.provinces.get(q) == enemy]
        return min(options, key=lambda q: self.garrison.get(q, 0)) if options else None

    def _ai(self, state: State, now: float) -> None:
        player = state.seat.nation
        # Hostile, strong leaders declare war on the player.
        if player and now >= self.next_declare:
            self.next_declare = now + AI_DECLARE_SECONDS
            mine = self.troops(player, state)
            for n in state.nations:
                if n == player or self.at_war(n, player) or self.pacts.get(relation_key(n, player), 0) > now:
                    continue
                rel = state.relations.get(relation_key(n, player), 0)
                if rel <= AI_DECLARE_RELATION and self.troops(n, state) >= 0.9 * mine:
                    self.declare(state, n, player)
                    break
        # AI nations at war attack their weakest enemy border province when they have the edge.
        for n in state.nations:
            if n == player or not self.enemies(n) or self.next_ai.get(n, 0) > now:
                continue
            self.next_ai[n] = now + AI_THINK_SECONDS
            best = None
            for enemy in self.enemies(n):
                for p, o in state.provinces.items():
                    if o != enemy:
                        continue
                    for q in NEIGHBOURS.get(p, []):
                        if state.provinces.get(q) != n:
                            continue
                        odds = self.garrison.get(q, 0) * SEND_SHARE / max(1.0, self.garrison.get(p, 0) * DUG_IN)
                        if best is None or odds > best[0]:
                            best = (odds, p, q)
            if best and best[0] > 1.15 and not any(a.owner == n for a in self.armies):
                try:
                    self.attack(state, n, best[1], src=best[2])
                except ValueError:
                    pass
            elif best and state.nations[n].stats.gdp > 30:
                try:
                    self.recruit(state, n, 800)
                except ValueError:
                    pass

    # --- the view for GET /war -----------------------------------------------------

    def view(self, state: State) -> dict[str, Any]:
        now = self.clock()
        return {
            "enabled": True,
            "player": state.seat.nation,
            "garrisons": {p: {"owner": state.provinces.get(p), "troops": round(t)}
                          for p, t in self.garrison.items() if state.provinces.get(p)},
            "capitals": CAPITALS,
            "armies": [{"id": a.id, "owner": a.owner, "from": a.src, "to": a.dst, "troops": round(a.troops),
                        "progress": round(min(1.0, max(0.0, (now - a.depart) / max(0.01, a.arrive - a.depart))), 3),
                        "eta_s": round(max(0.0, a.arrive - now), 2), "target": a.target} for a in self.armies],
            "wars": [{"a": w.a, "b": w.b, "started_turn": w.started_turn, "battles": w.battles,
                      "score": {w.a: w.score(w.a), w.b: w.score(w.b)},
                      "taken": {w.a: w.taken.get(w.a, 0), w.b: w.taken.get(w.b, 0)},
                      "lost": {w.a: round(w.lost.get(w.a, 0)), w.b: round(w.lost.get(w.b, 0))}}
                     for w in self.wars.values()],
            "troops": {n: round(self.troops(n, state)) for n in state.nations},
            "recruiting": [{"nation": n, "troops": round(t), "ready_in_s": round(r - now, 1)}
                           for r, n, t in self.recruits],
            "pacts": {k: round(v - now) for k, v in self.pacts.items() if v > now},
            "log": self.log[-60:],
        }
