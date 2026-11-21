"""The war-odds needle: rollouts with matched seeds. No model calls.

    futures(before, after) -> FuturesResponse

Each rollout plays out any running crisis and then `months` strategy months. Leaders
choose with probability proportional to exp((score + personality_bias) / temperature).
Rollout i uses the same seed with and without the deal, so the difference between the
two sides comes from the deal, not from luck.
"""

from __future__ import annotations

import hashlib
import os
import json
import math
import random
from typing import Optional

from contracts.models import NATION_IDS, Action, Advice, FuturesResponse, State
from engine.core import advise, step, weights

ESCALATION = {"declare_war", "set_tariff", "blockade", "mobilise", "close_port"}
WAITING = {"wait", "stay_out"}


def _bias(state: State, nation: str, action: Action) -> float:
    b = weights()["personality_bias"].get(nation, {})
    bias = 0.0
    if action.type in ESCALATION:
        bias += b.get("escalation", 0)
        beliefs = state.nations[nation].beliefs
        if beliefs and beliefs.trust_in_player < 0.3:  # holds a grudge against a promise breaker
            bias += b.get("against_promise_breaker", 0)
    if action.type in WAITING:
        bias += b.get("wait", 0)
    return bias


def choose(state: State, nation: str, advice: list[Advice], rng: random.Random, temperature: float) -> Optional[Action]:
    if not advice:
        return None
    logits = [(a.score + _bias(state, nation, a.action)) / temperature for a in advice]
    top = max(logits)
    return rng.choices([a.action for a in advice], weights=[math.exp(l - top) for l in logits])[0]


def at_war(state: State) -> bool:
    return any(l.type == "war" for l in state.links)


def rollout(state: State, seed: int, months: int, first: Optional[list[Action]] = None) -> bool:
    """True if a war is on at any point in the next `months` (after any crisis)."""
    temp = weights()["rollout"]["temperature"]
    rng = random.Random(f"rollout:{seed}")
    s, war, first = state, at_war(state), list(first or [])
    while s.phase == "crisis":
        c = s.crisis
        nxt = c.tick + 1
        actions = list(first)
        fixed = {a.by for a in first}
        for n in NATION_IDS:
            if n not in c.decisions and n not in fixed and c.deadlines.get(n) == nxt:
                a = choose(s, n, advise(s, n), rng, temp)
                if a:
                    actions.append(a)
        first = []
        s = step(s, actions, seed)
        war = war or at_war(s)
    for _ in range(months):
        fixed = {a.by for a in first}
        actions = list(first) + [a for n in NATION_IDS if n not in fixed
                                 for a in [choose(s, n, advise(s, n), rng, temp)] if a and a.type != "wait"]
        # Moves from advise() are legal already; a deal from the phone (first) is checked.
        s = step(s, actions, seed, check=bool(first))
        first = []
        war = war or at_war(s)
    return war


_CACHE: dict[str, float] = {}


def war_p(state: State, count: int, months: int, first: Optional[list[Action]] = None) -> float:
    """Cached by state, so a call's "before" (the previous call's "after") is free."""
    key = hashlib.sha256((state.model_dump_json() + json.dumps([a.model_dump() for a in first or []])
                          + f"|{count}|{months}").encode()).hexdigest()
    if key not in _CACHE:
        if len(_CACHE) > 500:
            _CACHE.clear()
        _CACHE[key] = sum(rollout(state, 1000 + i, months, first) for i in range(count)) / count
    return _CACHE[key]


def caption(before: float, after: float) -> str:
    b, a = round(before * 100), round(after * 100)
    if abs(a - b) < 3:
        return f"Your deal barely moves the odds of war: {b}% → {a}%."
    if a < b:
        return f"Your deal cuts the odds of war in six months from {b}% to {a}%."
    return f"Your deal raises the odds of war in six months from {b}% to {a}%."


def futures(before: State, after: State, first_after: Optional[list[Action]] = None,
            count: Optional[int] = None, months: Optional[int] = None) -> FuturesResponse:
    r = weights()["rollout"]
    # GAMBIT_ROLLOUTS lowers the count on a slow demo laptop (Reviewer, #27 14:07); default 200.
    count = count or int(os.environ.get("GAMBIT_ROLLOUTS") or r["count"])
    months = months or r["months"]
    b = war_p(before, count, months)
    a = war_p(after, count, months, first_after)
    return FuturesResponse(before={"war_p": round(b, 3)}, after={"war_p": round(a, 3)}, caption=caption(b, a))
