"""Done check for DECIDED 13:06 items (1) and (2), the agents side:
    python -m agents.test_strategy

1. strategize_all() on the example state: every AI leader gets a real strategy (not the
   persona fallback), timed.
2. decide() for Ostrava picks up the cached strategy (it appears in the prompt) and stays valid.
3. strategize() for One Berth writes a crisis strategy under its own cache key.
4. Mediator seat: speak_fast() and interpret() answer a mediator validly.
"""
import asyncio
import os
import time

from contracts.models import Seat

from . import fixtures, leaders, llm
from .personas import card


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    s = fixtures.state()
    t = time.perf_counter()
    strat = await leaders.strategize_all(s)
    t_all = time.perf_counter() - t
    fallback = [n for n, v in strat.items() if v in card(n)]
    print(f"1. strategize_all ({t_all:.1f}s), fallbacks {fallback}:")
    for n, v in strat.items():
        print(f"   {n:9s} {v}")

    view = fixtures.leader_view("ostrava", s)
    used = leaders._strategy_for(view, leaders._dump(s))
    out = await leaders.decide(view)
    print(f"2. decide(ostrava) with strategy={'yes' if used == strat.get('ostrava') else 'NO'}: "
          f"{out.actions[0].type if out.actions else 'wait'} | private: {out.private_intent}")

    c = fixtures.state("state.crisis")
    t = time.perf_counter()
    cs = await leaders.strategize(c, "kessaria")
    print(f"3. crisis strategy kessaria ({time.perf_counter() - t:.1f}s): {cs}")
    crisis_cached = leaders._strategy_for(fixtures.leader_view("kessaria", c), leaders._dump(c)) == cs

    m = s.model_copy(deep=True)
    m.seat = Seat(role="mediator", nation="valdoria")
    mv = fixtures.call_view("zarnia", "I speak for no one. What would Zarnia need to stand its troops down?", s=m)
    spoken = await leaders.speak_fast(mv)
    judged = await leaders.interpret(mv, spoken["reply_text"])
    print(f"4. mediator → zarnia: [{spoken['emotion']}] {spoken['reply_text']}  beliefs {judged.belief_updates.model_dump()}")

    ok = not fallback and len(strat) >= 4 and used == strat.get("ostrava") and crisis_cached and spoken["reply_text"]
    print(f"\nanswered by {llm.STATS['by_model']}")
    print("PASS" if ok else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
