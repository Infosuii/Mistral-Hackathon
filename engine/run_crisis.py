"""Play One Berth headless from a scripted set of player calls. No model calls.

    python -m engine.run_crisis --script bluff      # also: honest, interrupt, silent, all

Each script is a list of (tick, nation, CallOutput fields, interrupted). Calls happen
after the tick is reached, the way a player would answer during it.
"""

from __future__ import annotations

import argparse
import asyncio

from contracts.models import CallOutput
from engine.game import Game


def _call(promises=(), actions=(), trust=0.0, resolve=0.0):
    return CallOutput(reply_text="...", emotion="calm", promises=list(promises), actions=list(actions),
                      belief_updates={"trust_in_player": trust, "resolve_of_player": resolve})


BERTH = lambda to, when="all_day": {"to": to, "what": "berth", "when": when, "condition": None}

SCRIPTS = {
    "silent": [],
    "honest": [
        (1, "ostrava", _call([BERTH("ostrava", "morning")], trust=0.05), False),
        (2, "zarnia", _call([BERTH("zarnia", "afternoon")], trust=0.05), False),
        (3, "nordhaven", _call(actions=[{"type": "send_tugs", "by": "nordhaven"}]), False),
    ],
    "bluff": [
        (1, "ostrava", _call([BERTH("ostrava")], resolve=0.05), False),
        (3, "zarnia", _call([BERTH("zarnia")], resolve=0.05), False),
        (7, "ostrava", _call(trust=-0.1), False),
    ],
    "interrupt": [
        (1, "ostrava", _call([BERTH("ostrava")], resolve=0.05), False),
        (3, "zarnia", _call([BERTH("zarnia")], resolve=0.05), False),
        (7, "ostrava", _call(actions=[{"type": "wait", "by": "ostrava"}], resolve=0.1), True),
    ],
}


async def play(script: str, seed: int = 7, quiet: bool = False) -> dict:
    g = Game(seed=seed, use_agents=False, needle=False)
    g.start_crisis("one_berth")
    calls = SCRIPTS[script]
    seen = len(g.state.news)
    while g.state.phase == "crisis":
        s = await g.turn()
        tick = s.crisis.tick if s.crisis else "end"
        for t, to, out, interrupted in calls:
            if s.crisis and t == s.crisis.tick:
                g.apply_call(to, out, interrupted=interrupted)
        if not quiet:
            for item in g.state.news[seen:]:
                print(f"  [{tick}] {item.text}")
        seen = len(g.state.news)
    result = next(e for e in reversed(g.state.events) if e.type == "crisis_resolved")
    extra = result.model_extra
    return {"decisions": extra["decisions"], "holders": extra["holders"], "war": extra["war"],
            "trust": {n: g.state.nations[n].beliefs.trust_in_player for n in ("ostrava", "zarnia")}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="all", choices=[*SCRIPTS, "all"])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    for name in (SCRIPTS if args.script == "all" else [args.script]):
        print(f"== {name}")
        r = asyncio.run(play(name, args.seed, quiet=args.script == "all"))
        print(f"   decisions {r['decisions']}\n   docked {r['holders'] or 'nobody'}  war {r['war']}  trust {r['trust']}")


if __name__ == "__main__":
    main()
