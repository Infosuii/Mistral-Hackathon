"""Done check for A2:  python -m agents.test_phone

Ten player lines through the split phone path the voice code uses: speak_fast()
(spoken reply, timed) then interpret() (promises, actions, beliefs, in the background).
Passes if all ten give a valid reply of at most two sentences with an emotion from the
enum, and every interpret() returns a valid CallOutput.
"""
import asyncio
import os
import re
import time

from contracts.models import CallOutput

from . import fixtures, leaders, llm

S, C = "state", "state.crisis"
LINES = [  # nation, player line, interrupted, hesitation_ms, state
    ("ostrava", "General, Ostrava gets the berth all day. You have my word.", False, 400, C),
    ("ostrava", "Wait, General, before you announce anything, hear my offer.", True, 0, C),
    ("ostrava", "I... I suppose we could maybe look at half a day?", False, 4200, C),
    ("zarnia", "Chairman, the berth is yours in the morning if you stand your troops down.", False, 800, C),
    ("zarnia", "Stop. Your mobilisation ends today or Valdoria cuts grain to Zarnia.", True, 0, C),
    ("kessaria", "Your Majesty, what would it take to split the day between both ships?", False, 3200, C),
    ("kessaria", "Close the port to nobody and Valdoria pays the harbour fees twice over.", False, 600, C),
    ("nordhaven", "Chancellor, can your tugs open a second berth by noon? We will pay for them.", False, 500, C),
    ("nordhaven", "We would like a trade deal: our food for your chips, starting this month.", False, 700, S),
    ("ostrava", "If you put a tariff on us, we will answer with one of our own.", False, 300, S),
]


async def one(n, said, intr, hes, s):
    view = fixtures.call_view(n, said, intr, hes, fixtures.state(s))
    t = time.perf_counter()
    try:
        spoken = await leaders.speak_fast(view)
    except Exception as e:  # noqa: BLE001
        return n, said, None, None, time.perf_counter() - t, 0.0, f"speak_fast {type(e).__name__}: {e}"
    t_fast = time.perf_counter() - t
    t = time.perf_counter()
    try:
        out = await leaders.interpret(view, spoken["reply_text"])
        CallOutput.model_validate(out.model_dump(mode="json"))
        err = None
    except Exception as e:  # noqa: BLE001
        out, err = None, f"interpret {type(e).__name__}: {e}"
    return n, said, spoken, out, t_fast, time.perf_counter() - t, err


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    res = []
    for args in LINES:  # one at a time, like a real call; 2512 allows 30 requests a minute
        res.append(await one(*args))
        n, said, sp, out, tf, ti, err = res[-1]
        print(f"{n:9s} fast {tf:4.1f}s interpret {ti:4.1f}s  player: {said}")
        if sp:
            print(f"    [{sp['emotion']}] {sp['reply_text']}")
        if out:
            print(f"    promises {[p.model_dump() for p in out.promises]} actions {[a.type for a in out.actions]} "
                  f"beliefs {out.belief_updates.model_dump()} ends {out.ends_call}")
        if err:
            print(f"    FAIL {err[:200]}")
    good = [r for r in res if r[2] and r[3] and not r[6]
            and len(re.findall(r"[.!?](\s|$)", r[2]["reply_text"])) <= 2]
    fast = sorted(r[4] for r in res if r[2])
    interp = sorted(r[5] for r in res if r[3])
    print(f"\nvalid {len(good)}/10; speak_fast median {fast[len(fast) // 2]:.1f}s max {fast[-1]:.1f}s; "
          f"interpret median {interp[len(interp) // 2]:.1f}s max {interp[-1]:.1f}s; answered by {llm.STATS['by_model']}")
    print("PASS" if len(good) == 10 else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
