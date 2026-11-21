"""Reviewer's REQUEST on #28 (13:44): a leader should not defy a decisive recommendation
out of pride alone.   python -m agents.test_decisive [model]

One Berth, tick 7: Nordhaven sent the tugs at tick 5 (a second berth is open), Ostrava has
publicly committed to a blockade, and its advisers score dock 8.0, wait 7.0, blockade 2.2.
Eight decisions; passes if blockade is chosen at most once and the second berth is stated.
"""
import asyncio
import json
import os
import sys
from collections import Counter

from contracts.models import Advice

from . import fixtures, leaders, llm

ADVICE = [("dock", 8.0), ("wait", 7.0), ("blockade", 2.2)]


async def main() -> None:
    if len(sys.argv) > 1:
        llm.DECIDE_MODEL = sys.argv[1]
    s = fixtures.state("state.crisis")
    advice = [Advice.model_validate({"action": {"type": t, "by": "ostrava", "params": {}}, "score": sc}) for t, sc in ADVICE]
    view = fixtures.leader_view("ostrava", s).model_copy(update={"advice": advice})
    facts = leaders._crisis_facts(leaders._dump(s))
    print("facts shown:", facts)
    outs = await asyncio.gather(*(leaders.decide(view) for _ in range(8)), return_exceptions=True)
    picks = Counter()
    for o in outs:
        if isinstance(o, Exception):
            picks["error"] += 1
            continue
        a = o.actions[0].type if o.actions else "wait"
        picks[a] += 1
        print(f"  {a:9s} {o.reason}")
    ok = picks["blockade"] <= 1 and any("SECOND BERTH IS OPEN" in f for f in facts) and not picks["error"]
    print(f"\n{dict(picks)} (model {llm.DECIDE_MODEL})")
    print("PASS" if ok else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
