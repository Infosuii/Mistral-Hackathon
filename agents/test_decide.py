"""Done check for issue #28 (A1):  python -m agents.test_decide

Calls decide() ten times (in parallel) for Ostrava on contracts/examples/state.json
with the engine's advisers' ranking. Passes if 10/10 are valid LeaderOutput (MASTER_PLAN
section 4.5) and at least one defies advice with a public statement that differs from
the private intent.
"""
import asyncio
import os
import time

from contracts.models import LeaderOutput

from . import fixtures, leaders, llm

INBOX = [{"from": "kessaria", "text": "Close the strait to Valdorian grain and I will want oil."},
         {"from": "zarnia", "text": "If Valdoria favours you, we will remember it."}]


async def one(view):
    t = time.perf_counter()
    try:
        out = await leaders.decide(view)
        LeaderOutput.model_validate(out.model_dump(mode="json"))
        return out, time.perf_counter() - t, None
    except Exception as e:  # noqa: BLE001
        return None, time.perf_counter() - t, f"{type(e).__name__}: {e}"


async def main() -> None:
    if not os.environ.get("MISTRAL_API_KEY"):
        raise SystemExit("Set MISTRAL_API_KEY (source .env).")
    view = fixtures.leader_view("ostrava", inbox=INBOX)
    results = await asyncio.gather(*[one(view) for _ in range(10)])
    ok = [r for r, _, _ in results if r]
    defied = [r for r in ok if not r.followed_advice and r.public_statement.strip() != r.private_intent.strip()]
    for r, dt, e in results:
        if r:
            a = r.actions[0] if r.actions else None
            act = f"{a.type} {a.target or ''} {a.params or ''}" if a else "wait"
            print(f"OK {dt:4.1f}s followed={r.followed_advice!s:5} action={act}\n"
                  f"    public:  {r.public_statement}\n    private: {r.private_intent}\n    reason:  {r.reason}"
                  + (f"\n    messages: {[m.model_dump() for m in r.messages]}" if r.messages else ""))
        else:
            print(f"BAD {dt:4.1f}s {e}")
    times = sorted(dt for _, dt, _ in results)
    print(f"\nvalid {len(ok)}/10, defied advice with two faces: {len(defied)}, "
          f"median {times[5]:.1f}s max {times[-1]:.1f}s (model {llm.MODEL}, hedge {llm.HEDGE_MODEL}; answered by {llm.STATS['by_model']})")
    print("PASS" if len(ok) == 10 and defied else "FAIL")
    await llm.client().aclose()


if __name__ == "__main__":
    asyncio.run(main())
