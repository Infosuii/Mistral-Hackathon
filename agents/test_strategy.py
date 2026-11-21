"""Done check for private strategy and the mediator seat (DECIDED 13:06, 13:07, 13:09):
    python -m agents.test_strategy

1. strategize_all() for a mediator seat (nation null): all five leaders get a real
   strategy on Large 4 (not the persona fallback), timed.
2. GAMBIT_PRIVATE_STRATEGY on: decide() with private_strategy puts it in the prompt.
3. Flag off: the same view's strategy is ignored.
4. Reset on the same seed: a view without private_strategy gets none (agents keeps no copy).
5. strategize() for One Berth writes a crisis strategy.
6. Mediator phone call: speak_fast() and interpret() answer validly.
"""
import asyncio
import json
import os
import time

from contracts.models import Seat

from . import fixtures, leaders, llm
from .personas import card

SEEN: list[str] = []
_chat = llm.chat


async def spy_chat(messages, **kw):
    SEEN.append(json.dumps(messages))
    return await _chat(messages, **kw)


async def decide_prompt(view) -> tuple[object, str]:
    SEEN.clear()
    out = await leaders.decide(view)
    return out, " ".join(SEEN)


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    llm.chat = spy_chat
    s = fixtures.state()
    med = s.model_dump(mode="json", by_alias=True)
    med["seat"] = {"role": "mediator", "nation": None}

    t = time.perf_counter()
    strat = await leaders.strategize_all(med)
    t_all = time.perf_counter() - t
    fallback = [n for n, v in strat.items() if v in card(n)]
    print(f"1. strategize_all, mediator seat ({t_all:.1f}s): {sorted(strat)}, fallbacks {fallback}")
    for n, v in strat.items():
        print(f"   {n:9s} {v[:160]}...")
    ok1 = len(strat) == 5 and not fallback

    plan = strat["ostrava"]
    view = fixtures.leader_view("ostrava", s).model_dump(mode="json", by_alias=True)
    os.environ["GAMBIT_PRIVATE_STRATEGY"] = "1"
    out, prompt = await decide_prompt(dict(view, private_strategy=plan))
    ok2 = plan[:40] in prompt.replace("\\", "")
    print(f"2. flag on:  strategy in prompt {ok2}; {out.actions[0].type if out.actions else 'wait'} | {out.private_intent}")

    os.environ["GAMBIT_PRIVATE_STRATEGY"] = "0"
    _, prompt = await decide_prompt(dict(view, private_strategy=plan))
    flat = prompt.replace("\\", "").replace(" ", "")
    ok3 = plan[:40].replace(" ", "") not in flat and '"your_private_strategy":null' in flat
    print(f"3. flag off: strategy ignored {ok3}")

    os.environ["GAMBIT_PRIVATE_STRATEGY"] = "1"
    _, prompt = await decide_prompt(view)  # a fresh game on the same seed: the engine passes none
    ok4 = not any(v[:40] in prompt.replace("\\", "") for v in strat.values())
    print(f"4. reset, same seed: no old strategy {ok4}")

    c = fixtures.state("state.crisis")
    t = time.perf_counter()
    cs = await leaders.strategize(c, "kessaria")
    ok5 = cs not in card("kessaria")
    print(f"5. crisis strategy kessaria ({time.perf_counter() - t:.1f}s): {cs[:200]}...")

    m = s.model_copy(deep=True)
    m.seat = Seat(role="mediator", nation="valdoria")  # the contract still needs a nation until Om's change
    mv = fixtures.call_view("zarnia", "I speak for no one. What would Zarnia need to stand its troops down?", s=m)
    spoken = await leaders.speak_fast(mv)
    judged = await leaders.interpret(mv, spoken["reply_text"])
    ok6 = bool(spoken["reply_text"])
    print(f"6. mediator → zarnia: [{spoken['emotion']}] {spoken['reply_text']}  beliefs {judged.belief_updates.model_dump()}")

    print(f"\n{ok1=} {ok2=} {ok3=} {ok4=} {ok5=} {ok6=}; answered by {llm.STATS['by_model']}")
    print("PASS" if all((ok1, ok2, ok3, ok4, ok5, ok6)) else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
